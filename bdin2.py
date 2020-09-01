#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
import dbus
#~ from gi.repository import Gtk as gtk 
#~ from gi.repository import GLib as glib

import gtk, glib
import pynotify

#~ gi.require_version('AppIndicator3', '0.1')

#~ from gi.repository import AppIndicator3 as appindicator
import appindicator
from dbus.mainloop.glib import DBusGMainLoop
#~ from dbus.exceptions import DBusException

pynotify.init('BDin2')
nota=pynotify.Notification('')

def filter_opt(opt):
    """Remove ``None`` values from a dictionary."""
    return {k: glib.variant(*v) for k, v in opt.items() if v[1] is not None}

class UmountError(BaseException):
    pass

class MountError(BaseException):
    pass

class DetachError(BaseException):
    pass

class Device(object):

	def __init__(self, d):
		#~ print d
		self.d=d[0]
		device = d[0].get('Device')

				#~ props(device)
		#~ print 'device=', device, '\n'
		self.device = bytearray(device).replace(b'\x00', b'').decode('utf-8')
		self.drive=str(d[0].get('Drive'))

		self.label = str(d[0].get('IdLabel'))
		self.uuid = str(d[0].get('IdUUID'))
		self.size = str(d[0].get('Size'))
		#~ print self.drive, self.device, self.uuid
		self.fs=d[1]
		self.addr=d[2]
		#~ self.props = dbus.Interface(d, dbus.PROPERTIES_IFACE)

	def __repr__(self):
		return "{} on {} ({:.2f} GB)".format(self.label, self.fs_device, self.fs_size)

	@property
	def fs_size(self):
		return float(self.size)/1048576.0/1000

	@property
	def fs_device(s):
		return s.device

	#~ @property
	#~ def partition_slave(s):
		#~ return s.partition.get('Table')

	#~ @property
	#~ def is_partition(self):
		#~ p=self.partition.get('Name')
		#~ return len(p)>0
		

	@property
	def name(self):
		if len(self.label)>0:
			return self.label
		else:
			return self.uuid;

	"""@property
	def is_internal(self):
		return bool(self.props.Get("org.freedesktop.UDisks2.Device", 'DeviceIsSystemInternal'))"""

	@property
	def is_mounted(self):
		return bool(self.fs.get('MountPoints'))
		
	def mount(self):
		#~ print 'mount'
		bus = dbus.SystemBus()
		obj=bus.get_object("org.freedesktop.UDisks2", self.addr)
		f=dbus.Interface(obj, dbus_interface="org.freedesktop.UDisks2.Filesystem")
		try:
			return unicode(f.Mount(''))
		except dbus.DBusException, e:
			raise MountError(e.message)

	def unmount(self):
		#~ print 'unmount'
		bus = dbus.SystemBus()
		obj=bus.get_object("org.freedesktop.UDisks2", self.addr)
		f=dbus.Interface(obj, dbus_interface="org.freedesktop.UDisks2.Filesystem")
		try:
			return unicode(f.Unmount(''))
		except dbus.DBusException, e:
			#~ print e
			raise UmountError(e.message)
	
	def set_label(s):
		#~ print 'set label'
		bus = dbus.SystemBus()
		obj=bus.get_object("org.freedesktop.UDisks2", s.addr)
		f = dbus.Interface(obj, dbus_interface="org.freedesktop.UDisks2.Filesystem")
		b=dbus.Interface(obj, dbus_interface='org.freedesktop.UDisks2.Block')
				
		d=gtk.Dialog('Set label', None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		l=gtk.Label('Label')
		l.show()
		d.vbox.pack_start(l)
		entry=gtk.Entry()
		entry.set_text(s.name)
		entry.show()
		d.vbox.pack_start(entry)
		response = d.run()
				
		if response==gtk.RESPONSE_ACCEPT:
			f.SetLabel(entry.get_text(), {'auth.no_user_interaction': ('b', True),})
			print b.Rescan({'auth.no_user_interaction': ('b', True),})			
		d.destroy()
	
	def detach(self):
		#~ print 'detach'
		bus = dbus.SystemBus()
		obj=bus.get_object("org.freedesktop.UDisks2", self.drive)
		d = dbus.Interface(obj, dbus_interface="org.freedesktop.UDisks2.Drive")
		try:
			b=d.PowerOff({'auth.no_user_interaction': ('b', True),})
			print b
			return unicode(b)
		except dbus.DBusException, e:
			raise DetachError(e)

class UdiskManager(object):
	def __init__(self, callback):
		self.bus = dbus.SystemBus()
		self.proxy = self.bus.get_object("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2")
		self.iface = dbus.Interface(self.proxy, "org.freedesktop.DBus.ObjectManager")

		def add_callback( *args ):
			nota.update('BDin2', 'Device has been mounted')
			nota.show()
			callback()
		def remove_callback( *args ):
			nota.update('BDin2', 'Device has been unmounted')
			nota.show()
			callback()
		def detach_callback( *args ):
			nota.update('BDin2', 'Device has been detached')
			nota.show()
			callback()
		def changed_callback( *args ):
			nota.update('BDin2', 'Device has been changed')
			nota.show()
			callback()
		def properties_changed(*args):
			nota.update('BDin2', 'Proprties has been changed')
			nota.show()
			callback()

		self.iface.connect_to_signal('InterfacesAdded', add_callback)
		self.iface.connect_to_signal('InterfacesRemoved', remove_callback)
		self.iface.connect_to_signal('InterfacesChanged', changed_callback)
		self.iface.connect_to_signal('PropertiesChanged', properties_changed)

	def list_devices(self):
		#~ print 'list_devices'
		devices=[]
		bus = dbus.SystemBus()
		proxy = self.bus.get_object("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2")
		iface = dbus.Interface(proxy, "org.freedesktop.DBus.ObjectManager")
		i=iface.GetManagedObjects()
		for k,v in i.iteritems():
			d=v.get('org.freedesktop.UDisks2.Block', {})
			if d.get('IdUsage') == "filesystem" and not d.get('HintSystem') and not d.get('ReadOnly'):
				f=v.get('org.freedesktop.UDisks2.Filesystem', {})
				d=Device((d, f, k))
				devices.append(d)
		return devices

def display_exception(method):
	try:
		method()
	except (MountError, UmountError, DetachError), e:
		dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, str(e.message))
		dialog.set_title("Bdin2")
		dialog.run()
		dialog.destroy()

class App(object):
	def __init__(self):
		self.ind = appindicator.Indicator("bdin2","indicator-messages", appindicator.CATEGORY_APPLICATION_STATUS)
		#~ self.ind = appindicator.Indicator.new("bdin2","indicator-messages", appindicator.IndicatorCategory.APPLICATION_STATUS)
		self.ind.set_status(appindicator.STATUS_ACTIVE)
		#~ self.ind.set_status(appindicator.IndicatorStatus.ACTIVE)
		self.ind.set_icon(gtk.STOCK_HARDDISK)
		#set_icon("block-device")
		self.manager = UdiskManager(self.menu_setup)
		self.menu_setup()
		
	def menu_setup(self):
		self.menu = gtk.Menu()

		for dev in self.manager.list_devices():
			#~ print dev
			name = "{} on {} ({:.2f} GB)".format(dev.name, dev.fs_device, dev.fs_size)
			#~ dev.name, dev.device_file)
			item = gtk.MenuItem(name)
			item.show()
			d_e = display_exception
			
			submenu = gtk.Menu()
			
			if not dev.is_mounted:
				#~ submenu = gtk.Menu()
				mount_item = gtk.ImageMenuItem("Mount")
				mount_item.show()
				mount_item.connect("activate", lambda i,d: d_e(d.mount), dev)
				submenu.append(mount_item)
				detach_item = gtk.ImageMenuItem("Detach")
				detach_item.show()
				detach_item.connect("activate", lambda i,d: d_e(d.detach), dev)
				submenu.append(detach_item)
				
				#~ l_item=gtk.ImageMenuItem("Set label")
				#~ l_item.show()
				#~ l_item.connect("activate", lambda i,d: d_e(d.set_label), dev)
				#~ submenu.append(l_item)
				
			else:
				#~ submenu = gtk.Menu()
				unmount_item = gtk.ImageMenuItem("Unmount")
				unmount_item.show()
				unmount_item.connect("activate", lambda i,d : d_e(d.unmount), dev)
				submenu.append(unmount_item)
				
				#~ l_item=gtk.ImageMenuItem("Set label")
				#~ l_item.show()
				#~ l_item.connect("activate", lambda i,d: d_e(d.set_label), dev)
				#~ submenu.append(l_item)
			submenu.append(gtk.SeparatorMenuItem())
			l_item=gtk.ImageMenuItem("Set label")
			l_item.show()
			l_item.connect("activate", lambda i,d: d_e(d.set_label), dev)
			submenu.append(l_item)
			
			item.set_submenu(submenu)
			self.menu.append(item)

		#~ sep=gtk.SeparatorMenuItem()
		#~ sep.show()
		self.menu.append(gtk.SeparatorMenuItem())
		about = gtk.ImageMenuItem("About")
		img = gtk.Image()
		img.set_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
		#~ img.set_from_stock(gtk.STOCK_ABOUT, gtk.IconSize.MENU)
		about.set_image(img)
		about.connect('activate', lambda i: self.show_about())
		about.show()
		self.menu.append(about)
		image = gtk.ImageMenuItem(gtk.STOCK_QUIT)
		image.connect("activate", self.quit)
		image.show()
		self.menu.append(image)
		self.menu.show_all()
		self.ind.set_menu(self.menu)

	def quit(self, widget, data=None):
		gtk.main_quit()


	def show_about(self):
		self.about = gtk.AboutDialog()
		self.about.set_name("Bdin2")
		self.about.set_version("0.0.2b")
		self.about.set_comments("A block device appindicator for ubuntu or Debian\nFork and legacy of bdin from Rodrigo Pinheiro Marques de Araujo")
		self.about.set_copyright("ghoul.mask")
		self.about.set_program_name("Bdin2")
		self.about.set_website("https://github.com/u-chu/bdin2")
		self.about.run()
		self.about.destroy()

def main():
	DBusGMainLoop(set_as_default=True)
	app = App()
	gtk.main()

if __name__ == "__main__":
    main()
