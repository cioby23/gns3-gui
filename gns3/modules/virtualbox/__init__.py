# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
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

"""
VirtualBox module implementation.
"""

from gns3.qt import QtCore, QtGui
from gns3.local_server_config import LocalServerConfig

from ..module import Module
from ..module_error import ModuleError
from .virtualbox_vm import VirtualBoxVM
from .settings import VBOX_SETTINGS, VBOX_SETTING_TYPES
from .settings import VBOX_VM_SETTINGS, VBOX_VM_SETTING_TYPES

import logging
log = logging.getLogger(__name__)


class VirtualBox(Module):

    """
    VirtualBox module.
    """

    def __init__(self):
        Module.__init__(self)

        self._settings = {}
        self._virtualbox_vms = {}
        self._nodes = []
        self._working_dir = ""

        # load the settings
        self._loadSettings()
        self._loadVirtualBoxVMs()

    def _loadSettings(self):
        """
        Loads the settings from the server settings file.
        """

        # load the settings
        config = LocalServerConfig.instance()
        self._settings = config.loadSettings(self.__class__.__name__, VBOX_SETTINGS, VBOX_SETTING_TYPES)

    def _saveSettings(self):
        """
        Saves the settings to the server settings file.
        """

        # save the settings
        config = LocalServerConfig.instance()
        config.saveSettings(self.__class__.__name__, self._settings)

    def _loadVirtualBoxVMs(self):
        """
        Load the VirtualBox VMs from the client settings file.
        """

        # load the settings
        settings = QtCore.QSettings()
        settings.beginGroup("VirtualBoxVMs")

        # load the VMs
        size = settings.beginReadArray("VM")
        for index in range(0, size):
            settings.setArrayIndex(index)
            vmname = settings.value("vmname")
            server = settings.value("server")
            key = "{server}:{vmname}".format(server=server, vmname=vmname)
            if key in self._virtualbox_vms or not vmname or not server:
                continue
            self._virtualbox_vms[key] = {}
            for setting_name, default_value in VBOX_VM_SETTINGS.items():
                self._virtualbox_vms[key][setting_name] = settings.value(setting_name, default_value, VBOX_VM_SETTING_TYPES[setting_name])

        settings.endArray()
        settings.endGroup()

    def _saveVirtualBoxVMs(self):
        """
        Saves the VirtualBox VMs to the client settings file.
        """

        # save the settings
        settings = QtCore.QSettings()
        settings.beginGroup("VirtualBoxVMs")
        settings.remove("")

        # save the VirtualBox VMs
        settings.beginWriteArray("VM", len(self._virtualbox_vms))
        index = 0
        for vbox_vm in self._virtualbox_vms.values():
            settings.setArrayIndex(index)
            for name, value in vbox_vm.items():
                settings.setValue(name, value)
            index += 1
        settings.endArray()
        settings.endGroup()

    def virtualBoxVMs(self):
        """
        Returns VirtualBox VMs settings.

        :returns: VirtualBox VMs settings (dictionary)
        """

        return self._virtualbox_vms

    def setVirtualBoxVMs(self, new_virtualbox_vms):
        """
        Sets VirtualBox VM settings.

        :param new_iou_images: IOS images settings (dictionary)
        """

        self._virtualbox_vms = new_virtualbox_vms.copy()
        self._saveVirtualBoxVMs()

    def addNode(self, node):
        """
        Adds a node to this module.

        :param node: Node instance
        """

        self._nodes.append(node)

    def removeNode(self, node):
        """
        Removes a node from this module.

        :param node: Node instance
        """

        if node in self._nodes:
            self._nodes.remove(node)

    def settings(self):
        """
        Returns the module settings

        :returns: module settings (dictionary)
        """

        return self._settings

    def setSettings(self, settings):
        """
        Sets the module settings

        :param settings: module settings (dictionary)
        """

        self._settings.update(settings)
        self._saveSettings()

    def createNode(self, node_class, server, project):
        """
        Creates a new node.

        :param node_class: Node object
        :param server: WebSocketClient instance
        :param project: Project instance
        """

        log.info("creating node {}".format(node_class))

        if not server.connected():
            try:
                log.info("reconnecting to server {}:{}".format(server.host, server.port))
                server.reconnect()
            except OSError as e:
                raise ModuleError("Could not connect to server {}:{}: {}".format(server.host,
                                                                                 server.port,
                                                                                 e))

        # create an instance of the node class
        return node_class(self, server, project)

    def setupNode(self, node, node_name):
        """
        Setups a node.

        :param node: Node instance
        :param node_name: Node name
        """

        log.info("configuring node {} with id {}".format(node, node.id()))

        vm = None
        if node_name:
            for vm_key, info in self._virtualbox_vms.items():
                if node_name == info["vmname"]:
                    vm = vm_key

        if not vm:
            selected_vms = []
            for vm, info in self._virtualbox_vms.items():
                if info["server"] == node.server().host or (node.server().isLocal() and info["server"] == "local"):
                    selected_vms.append(vm)

            if not selected_vms:
                raise ModuleError("No VirtualBox VM on server {}".format(node.server().host))
            elif len(selected_vms) > 1:

                from gns3.main_window import MainWindow
                mainwindow = MainWindow.instance()

                (selection, ok) = QtGui.QInputDialog.getItem(mainwindow, "VirtualBox VM", "Please choose a VM", selected_vms, 0, False)
                if ok:
                    vm = selection
                else:
                    raise ModuleError("Please select a VirtualBox VM")

            else:
                vm = selected_vms[0]

        linked_base = self._virtualbox_vms[vm]["linked_base"]
        if not linked_base:
            for other_node in self._nodes:
                if other_node.settings()["vmname"] == self._virtualbox_vms[vm]["vmname"] and \
                        (self._virtualbox_vms[vm]["server"] == "local" and other_node.server().isLocal() or self._virtualbox_vms[vm]["server"] == other_node.server().host):
                    raise ModuleError("Sorry a VirtualBox VM can only be used once in your topology (this will change in future versions)")

        settings = {}
        for setting_name, value in self._virtualbox_vms[vm].items():
            if setting_name in node.settings():
                settings[setting_name] = value

        vmname = self._virtualbox_vms[vm]["vmname"]
        node.setup(vmname, linked_clone=linked_base, additional_settings=settings)

    def reset(self):
        """
        Resets the module.
        """

        self._nodes.clear()

    @staticmethod
    def getNodeClass(name):
        """
        Returns the object with the corresponding name.

        :param name: object name
        """

        if name in globals():
            return globals()[name]
        return None

    @staticmethod
    def classes():
        """
        Returns all the node classes supported by this module.

        :returns: list of classes
        """

        return [VirtualBoxVM]

    def nodes(self):
        """
        Returns all the node data necessary to represent a node
        in the nodes view and create a node on the scene.
        """

        nodes = []
        for vbox_vm in self._virtualbox_vms.values():
            nodes.append(
                {"class": VirtualBoxVM.__name__,
                 "name": vbox_vm["vmname"],
                 "server": vbox_vm["server"],
                 "categories": VirtualBoxVM.categories(),
                 "default_symbol": vbox_vm["default_symbol"],
                 "hover_symbol": vbox_vm["hover_symbol"],
                 "categories": [vbox_vm["category"]]}
            )
        return nodes

    @staticmethod
    def preferencePages():
        """
        :returns: QWidget object list
        """

        from .pages.virtualbox_preferences_page import VirtualBoxPreferencesPage
        from .pages.virtualbox_vm_preferences_page import VirtualBoxVMPreferencesPage
        return [VirtualBoxPreferencesPage, VirtualBoxVMPreferencesPage]

    @staticmethod
    def instance():
        """
        Singleton to return only one instance of VirtualBox module.

        :returns: instance of VirtualBox
        """

        if not hasattr(VirtualBox, "_instance"):
            VirtualBox._instance = VirtualBox()
        return VirtualBox._instance
