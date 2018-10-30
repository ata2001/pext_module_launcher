#!/usr/bin/env python3

# Copyright (C) 2016 - 2017 Sylvia van Os <sylvia@hackerchick.me>
#
# Pext launcher module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import configparser
import html
import platform
import shlex

from distutils.util import strtobool
from os import access, environ, listdir, pathsep, X_OK
from os.path import expanduser, isfile, join
from re import sub
from subprocess import Popen

from pext_base import ModuleBase
from pext_helpers import Action


class Module(ModuleBase):
    def init(self, settings, q):
        self.use_path = False if ('use_path' not in settings) else bool(strtobool(settings['use_path']))

        self.executables = []
        self.info_panels = {}
        self.context_menus = {}

        self.settings = settings
        self.q = q

        self._get_entries()

    def get_executables(self, paths=None, windows=False):
        if paths is None:
            paths = environ['PATH'].split(pathsep)

        for path in paths:
            path = expanduser(path)
            try:
                for executable in listdir(path):
                    fullname = join(path, executable)
                    if isfile(fullname):
                        if windows:
                            if not executable.endswith('.exe'):
                                continue
                        else:
                            if not access(fullname, X_OK):
                                continue

                        if executable not in self.executables:
                            self.executables.append(executable)
                            self.info_panels[executable] = "<b>{}</b>".format(html.escape(fullname))
                            self.context_menus[executable] = [fullname]
                        else:
                            self.info_panels[executable] += "<br/>{}".format(html.escape(fullname))
                            self.context_menus[executable].append(fullname)
            except OSError:
                pass

    def _get_entries(self):
        if platform.system() == 'Darwin':
            if self.use_path:
                self.get_executables()
            else:
                for executable in listdir('/Applications'):
                    if not executable.endswith('.app'):
                        continue

                    self.executables.append(executable.rstrip('.app'))
        elif platform.system() == 'Linux':
            if self.use_path:
                self.get_executables()
            else:
                try:
                    xdg_data_dirs = environ['XDG_DATA_DIRS'].split(pathsep)
                except KeyError:
                    xdg_data_dirs = ['/usr/share', '/usr/local/share']

                for directory in xdg_data_dirs:
                    directory = join(expanduser(directory), 'applications')
                    try:
                        for desktop_entry in listdir(directory):
                            desktop_entry = join(directory, desktop_entry)

                            parser = configparser.RawConfigParser()
                            parser.read(desktop_entry)
                            try:
                                app = parser['Desktop Entry']['Name']
                                command = parser['Desktop Entry']['Exec']
                            except KeyError:
                                continue

                            # FIXME: Calling executable without args
                            command = sub(r'%[fFuUick]', '', command)

                            if app not in self.executables:
                                self.executables.append(app)
                                self.info_panels[app] = "<b>{}</b>".format(html.escape(command))
                                self.context_menus[app] = [command]
                            elif command not in self.context_menus[app]:
                                self.info_panels[app] += "<br/>{}".format(html.escape(command))
                                self.context_menus[app].append(command)
                    except OSError:
                        pass
        elif platform.system() == 'Windows':
            if self.use_path:
                self.get_executables(windows=True)
            else:
                import wmi
                w = wmi.WMI()
                paths = [p.InstallLocation for p in w.Win32_Product()]
                self.get_executables(paths, windows=True)

        self.executables.sort()
        self._set_entries()

    def _set_entries(self):
        if not self.use_path and platform.system() == 'Darwin':
            self.q.put([Action.replace_command_list, []])
            self.q.put([Action.replace_entry_list, self.executables])
        else:
            self.q.put([Action.replace_command_list, self.executables])
            self.q.put([Action.replace_entry_list, []])

        if self.settings['_api_version'] >= [0, 5, 0]:
            self.q.put([Action.replace_command_info_dict, self.info_panels])
            self.q.put([Action.replace_command_context_dict, self.context_menus])

    def stop(self):
        pass

    def selection_made(self, selection):
        if len(selection) == 0:
            self._set_entries()
        elif len(selection) == 1:
            if self.settings['_api_version'] >= [0, 8, 0]:
                command = " ".join((selection[0]["value"], selection[0]["args"]))
            else:
                command = selection[0]["value"]

            if not self.use_path and platform.system() == 'Darwin':
                Popen(["open", "-a", "{}".format(command)])
            elif not self.use_path and platform.system() == 'Linux':
                command = shlex.split(
                        selection[0]['context_option'] if selection[0]['context_option']
                        else self.context_menus[selection[0]['value']][0])
                Popen(command)
            else:
                command = shlex.split(command)
                if self.settings['_api_version'] >= [0, 4, 0]:
                    if selection[0]['context_option']:
                        command[0] = selection[0]['context_option']

                Popen(command)

            self.q.put([Action.close])

    def process_response(self, response):
        pass
