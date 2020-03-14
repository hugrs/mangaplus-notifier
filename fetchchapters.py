#!/usr/bin/env python3
import http.client
import re
import sys
import os
from datetime import datetime,date
from pathlib import Path
import proto.title_detail_pb2 as title_detail_pb2
import gi
gi.require_version("Gtk","3.0")
gi.require_version("Gio","2.0")
from gi.repository import Gtk, Gio

DATA_DIR = os.path.join(Path.home(), ".mangaplus")
BLOB_FILE = os.path.join(DATA_DIR, "response-blob")

def fetch_and_save_title_info():
    conn = http.client.HTTPSConnection("jumpg-webapi.tokyo-cdn.com")
    print("Making GET request to /api/title_detail")
    conn.request("GET", "/api/title_detail?title_id=100056")

    res = conn.getresponse()
    print("Request complete, saving response into file...")
    with open(BLOB_FILE, "wb") as blob:
        blob.write(res.read())
    print("Success!")
    conn.close()

def read_blob():
    with open(BLOB_FILE, "rb") as blob:
        response = title_detail_pb2.Response()
        response.ParseFromString(blob.read())
    if response.HasField("error"):
        print(response.error)
        sys.exit(1)
    return response.success.titleDetailView

def get_latest_chapter(title_info):
    if len(title_info.lastChapterList) > 0:
        chapter_list = title_info.lastChapterList
    else:
        chapter_list = title_info.firstChapterList
    latest_chapter = chapter_list[-1]
    latest_chapter_id = max([c.chapterId for c in chapter_list])
    if latest_chapter.chapterId != latest_chapter_id:
        print("Warning: last entry in chapter list is not the latest chapter")
        print("Consider fixing the script to retrieve the chapter differently")
    return latest_chapter


class Application(Gtk.Application):
    APP_ID = "com.swarm.mangaplusfetcher"

    def __init__(self):
        if not Gtk.Application.id_is_valid(self.APP_ID):
            print("Application ID invalid", self.APP_ID)
            sys.exit(1)
        super().__init__(application_id=self.APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("startup", self.on_startup)
        self.connect("activate", self.on_activate)
        self.hold()

    def on_startup(self, application):
        print("Startup")
        action_dismiss = Gio.SimpleAction.new("dismiss")
        action_dismiss.connect("activate", self.on_action_dismiss)
        self.add_action(action_dismiss)

    def on_activate(self, application):
        print("Activated")
        self.show_notification("notif-test", "Title", "Body")

    def on_action_dismiss(self, action, parameter):
        print("bozo")
        self.release()

    def show_notification(self, id, title, body):
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.add_button("Dismiss", "app.dismiss")
        self.send_notification(id, notification)


app = Application()
app.run()

# Create hidden directory under $HOME
if not os.path.isdir(DATA_DIR):
    os.mkdir(DATA_DIR)
# If cached response blob is not found, fetch from the server then display latest chapter and exit
if not os.path.isfile(BLOB_FILE):
    fetch_and_save_title_info()
    latest_chapter = get_latest_chapter(read_blob())
    app.show_notification("latest-chapter",
        "SPYxFAMILY"
        f"Latest chapter: {latest_chapter.subTitle}\nReleased on {datetime.fromtimestamp(latest_chapter.startTimeStamp)}")
    sys.exit(0)

title_info = read_blob()
current_chapter = get_latest_chapter(title_info)
date_current_chapter = datetime.fromtimestamp(current_chapter.startTimeStamp)
print(f"Current last chapter: {current_chapter.name} ({date_current_chapter.date()})")
date_next_release = datetime.fromtimestamp(title_info.nextTimestamp)
print(f"Next chapter releases on {date_next_release}")

if datetime.now() > date_next_release:
    print(f"Last release date was {date_next_release}, a new chapter should be released by now...")
    fetch_and_save_title_info()

    new_chapter = get_latest_chapter(read_blob())
    date_new_chapter = datetime.fromtimestamp(new_chapter.startTimeStamp)
    if date_new_chapter > date_current_chapter:
        print(f"A new chapter has been released! {new_chapter.name} - {new_chapter.subTitle}")
        print(f"Released on {date_new_chapter}")
        app.show_notification("new-chapter",
            "SPYxFAMILY"
            f"A new chapter has been released!\n{new_chapter.subTitle}")