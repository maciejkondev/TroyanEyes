import json
import os

import sys

class ProfileManager:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            # Running as compiled EXE
            base_path = os.path.dirname(sys.executable)
            self.data_dir = os.path.join(base_path, 'data')
        else:
            # Running from source
            self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
            
        self.file_path = os.path.join(self.data_dir, 'profiles.json')
        self.profiles = {}
        self.last_used = None
        self._ensure_file()
        self.load_profiles()

    def _ensure_file(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if not os.path.exists(self.file_path):
            self.save_data()

    def load_profiles(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.profiles = data.get("profiles", {})
                self.last_used = data.get("last_used")
        except (FileNotFoundError, json.JSONDecodeError):
            self.profiles = {}
            self.last_used = None

    def save_data(self):
        data = {
            "profiles": self.profiles,
            "last_used": self.last_used
        }
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=4)

    def get_profile_names(self):
        return list(self.profiles.keys())

    def get_profile(self, name):
        return self.profiles.get(name, {})

    def save_profile(self, name, data):
        self.profiles[name] = data
        self.last_used = name
        self.save_data()

    def delete_profile(self, name):
        if name in self.profiles:
            del self.profiles[name]
            if self.last_used == name:
                self.last_used = None if not self.profiles else list(self.profiles.keys())[0]
            self.save_data()

    def set_last_used(self, name):
        if name in self.profiles:
            self.last_used = name
            self.save_data()
