#!/usr/bin/env python3
import http.client
import sys
import os
import json
from datetime import datetime,date
from pathlib import Path
import proto.title_detail_pb2 as title_detail_pb2
import gi
gi.require_version("Gtk","3.0")
gi.require_version("Gio","2.0")
gi.require_version("GLib","2.0")
from gi.repository import Gtk, Gio, GLib

DATA_DIR = os.path.join(Path.home(), ".mangaplus")
BLOB_FILE = os.path.join(DATA_DIR, "response-cache")
META_FILE = os.path.join(DATA_DIR, "metadata")

class Title:
    def __init__(self, response_proto):
        response = title_detail_pb2.Response()
        response.ParseFromString(response_proto)
        if response.HasField("error"):
            print(response.error)
            sys.exit(1)
        self.detail = response.success.titleDetailView
        
    def get_latest_chapter(self):
        if len(self.detail.lastChapterList) > 0:
            chapter_list = self.detail.lastChapterList
        else:
            chapter_list = self.detail.firstChapterList
        latest_chapter = chapter_list[-1]
        latest_chapter_id = max([c.chapterId for c in chapter_list])
        if latest_chapter.chapterId != latest_chapter_id:
            print("Warning: last entry in chapter list is not the latest chapter")
            print("Consider fixing the script to retrieve the chapter differently")
        return latest_chapter
    
    def get_next_release_date(self):
        return datetime.fromtimestamp(self.detail.nextTimestamp)

def fetch_and_save_title_info():
    conn = http.client.HTTPSConnection("jumpg-webapi.tokyo-cdn.com")
    print("Making GET request to /api/title_detail")
    conn.request("GET", "/api/title_detail?title_id=100056")

    proto_blob = conn.getresponse().read()
    print("Request complete, saving response into file...")
    with open(BLOB_FILE, "wb") as file:
        file.write(proto_blob)
    print("Success!")
    conn.close()
    return Title(proto_blob)

def save_metadata(data):
    # Check that data is correctly formed to not erase previous metadata with corrupt data
    if "last_acknowledged_chapter" in data:
        with open(META_FILE, "w") as file:
            json.dump(data, file)
  


class Application(Gtk.Application):
    APP_ID = "com.swarm.mangaplusfetcher"

    def __init__(self):
        if not Gtk.Application.id_is_valid(self.APP_ID):
            print("Application ID invalid", self.APP_ID)
            sys.exit(1)
        super().__init__(application_id=self.APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("startup", self.on_startup)
        self.connect("activate", self.main)

    def on_startup(self, application):
        action_default = Gio.SimpleAction.new("notification.clicked")
        action_default.connect("activate", self.notification_acknowledge)
        self.add_action(action_default)

    def timeout_callback(self):
        self.release()
        return False

    def notification_acknowledge(self, action, parameter):
        with open(BLOB_FILE, "rb") as blob:
            title_info = Title(blob.read())
        save_metadata({"last_acknowledged_chapter": title_info.get_latest_chapter().name})
        print("Dismissed!")
        self.release()

    def show_notification(self, id, title, body, wait_for_dismiss=False):
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        if wait_for_dismiss:
            notification.set_default_action("app.notification.clicked")
            GLib.timeout_add_seconds(30, self.timeout_callback)
            self.hold()
        self.send_notification(id, notification)

    def main(self, application):
        # Create hidden directory under $HOME
        if not os.path.isdir(DATA_DIR):
            os.mkdir(DATA_DIR)
        # If cached response blob is not found, fetch from the server then display latest chapter and exit
        if not os.path.isfile(BLOB_FILE) or not os.path.isfile(META_FILE):
            title_info = fetch_and_save_title_info()
            latest_chapter = title_info.get_latest_chapter()
            save_metadata({"last_acknowledged_chapter": latest_chapter.name})
            
            self.show_notification("latest-chapter",
                "SPYxFAMILY",
                f"Latest chapter: {latest_chapter.subTitle}\nReleased on {datetime.fromtimestamp(latest_chapter.startTimeStamp)}")
            return

        with open(BLOB_FILE, "rb") as blob:
            title_info = Title(blob.read())
        current_chapter = title_info.get_latest_chapter()
        self.current_chapter = current_chapter
        date_current_chapter = datetime.fromtimestamp(current_chapter.startTimeStamp)
        print(f"Current last chapter: {current_chapter.name} ({date_current_chapter.date()})")
        date_next_release = title_info.get_next_release_date()
        print(f"Next chapter releases on {date_next_release}")

        if datetime.now() > date_next_release:
            print(f"Last release date was {date_next_release}, a new chapter should be released by now...")
            title_info = fetch_and_save_title_info()
            current_chapter = title_info.get_latest_chapter()

        with open(META_FILE, "r") as file:
            metadata = json.load(file)
            if current_chapter.name != metadata["last_acknowledged_chapter"]:
                self.show_notification("new-chapter",
                    "SPYxFAMILY",
                    f"A new chapter has been released!\n{current_chapter.subTitle}",
                    wait_for_dismiss=True)


app = Application()
app.run()