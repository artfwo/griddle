#! /usr/bin/env python
# meme - a serialosc-compatible gtk monome emulator -- work in progress

import gtk, gobject

#import liblo
from liblo import *
import select, pybonjour
REGTYPE = "_monome-osc._udp"
NAME_FORMAT = "meme-%d"

class Justosc(Server):
    def __init__(self, port, gui):
        Server.__init__(self, port=port)
        self.prefix = "/box"
        self.gui = gui
    
    @make_method('/sys/prefix', 's')
    def sys_prefix(self, path, args):
        prefix, = args
        self.prefix = "/%s" % prefix.strip("/")
        self.register_callbacks()
    
    def register_callbacks(self):
        self.add_method("%s/grid/led/set" % self.prefix, "iii", self.grid_led_set)

    def grid_led_set(self, path, args):
        x, y, s = args
        if s == 1:
            self.gui.light_button(x, y)
        else:
            self.gui.unlight_button(x, y)

class Meme(Server):
    def __init__(self, port, gui):
        self.server = Justosc(port, gui)
        #self.gui = gui
        self.sdRef = pybonjour.DNSServiceRegister(name = NAME_FORMAT % port,
             regtype = REGTYPE,
             port = port,
             callBack = self.register_callback)
    
    def register_callback(self, sdRef, flags, errorCode, name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            print 'Registered service:', name, regtype, domain
            #self.waffle = Waffle(20000)
            #self.waffle.start()
            pass
    
    def poll(self):
        ready = select.select([self.sdRef], [], [], 0)
        if self.sdRef in ready[0]:
            pybonjour.DNSServiceProcessResult(self.sdRef)
        self.server.recv(0)
    
    def close(self):
        self.sdRef.close()

class MemeGui(gtk.Window):
    def __init__(self, port, xsize, ysize):
        gtk.Window.__init__(self)
        self.s = Meme(port, self)
        self.set_title(NAME_FORMAT % port)
        
        self.buttons = [[gtk.Button() for y in range(ysize)] for x in range(xsize)]
        #for y in range(ysize):
        #    buttons.append([gtk.Button() for x in range(xsize)])
        
        table = gtk.Table(homogeneous=True)
        self.add(table)
        table.props.row_spacing = 6
        table.props.column_spacing = 6
        table.props.border_width = 6
        
        for x in range(xsize):
            for y in range(ysize):
                table.attach(self.buttons[x][y], x, x+1, y, y+1)
                b = self.buttons[x][y]
                b.set_size_request(32,32)
                b.connect("clicked", self.button_clicked, x, y)
                self.unlight_button(x, y)
        
        #self.set_default_size(320, 320)
        gobject.idle_add(self.idle)
    
    def idle(self):
        self.s.poll()
        return True
    
    def button_clicked(self, b, x, y):
        print "clicked", b, x, y
    
    def light_button(self, x, y):
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#880000"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aa0000"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ff0000"))
    
    def unlight_button(self, x, y):
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#888888"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aaaaaa"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ffffff"))
    
    def do_delete_event(self, *args):
        self.s.close()
        gtk.main_quit()

gobject.type_register(MemeGui)

w = MemeGui(10000, 16, 16)
w.show_all()
gtk.main()

