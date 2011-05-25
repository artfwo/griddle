#! /usr/bin/env python
# meme - a serialosc-compatible gtk monome emulator -- work in progress

import gtk, gobject

import liblo
from liblo import *
import select, pybonjour
REGTYPE = "_monome-osc._udp"
NAME_FORMAT = "meme-%d"

def bitarray(b):
    #return [b>>7&1, b>>6&1, b>>5&1, b>>4&1, b>>3&1, b>>2&1, b>>1&1, b&1]
    return [b&1, b>>1&1, b>>2&1, b>>3&1, b>>4&1, b>>5&1, b>>6&1, b>>7&1]

class Justosc(Server):
    def __init__(self, port, gui):
        Server.__init__(self, port=port)
        self.app_port = 8000
        self.app_host = "localhost"
        self.prefix = "/monome" # /monome
        self.rotation = 0 # FIXME
        self.gui = gui
        self.register_callbacks(self.prefix)
    
    @make_method('/sys/port', 'i')
    def sys_port(self, path, args):
        port, = args
        self.app_port = port
    
    @make_method('/sys/host', 's')
    def sys_port(self, path, args):
        host, = args
        self.app_host = host
    
    @make_method('/sys/prefix', 's')
    def sys_prefix(self, path, args):
        prefix, = args
        self.unregister_callbacks(self.prefix)
        self.prefix = "/%s" % prefix.strip("/")
        self.register_callbacks(self.prefix)
    
    @make_method('/sys/info', None)
    def sys_prefix(self, path, args):
        if len(args) == 2:
            host, port = args
        elif len(args) == 1:
            host, port = self.app_host, args[0]
        elif len(args) == 0:
            host, port = self.app_host, self.app_port
        else:
            return
        target = liblo.Address(host, port)
        liblo.send(target, "/sys/port", port)
        liblo.send(target, "/sys/host", host)
        liblo.send(target, "/sys/id", "meme")
        liblo.send(target, "/sys/prefix", self.prefix)
    
    def unregister_callbacks(self, prefix):
        self.del_method("%s/grid/led/set" % prefix, "iii")
        self.del_method("%s/grid/led/map" % prefix, "iiiiiiiiii")
        self.del_method("%s/grid/led/row" % prefix, None)
        self.del_method("%s/grid/led/col" % prefix, None)
    
    def register_callbacks(self, prefix):
        self.add_method("%s/grid/led/set" % prefix, "iii", self.grid_led_set)
        self.add_method("%s/grid/led/map" % prefix, "iiiiiiiiii", self.grid_led_map)
        self.add_method("%s/grid/led/row" % prefix, None, self.grid_led_row)
        self.add_method("%s/grid/led/col" % prefix, None, self.grid_led_col)

    def grid_led_set(self, path, args):
        x, y, s = args
        if s == 1:
            self.gui.light_button(x, y)
        else:
            self.gui.unlight_button(x, y)
    
    def grid_led_map(self, path, args):
        x_offset = args[0]
        y_offset = args[1]
        s = args[2:]
        for i in range(len(s)):
            self.grid_led_row(None, [x_offset, y_offset+i, s[i]])
    
    # FIXME: need len(args) check
    def grid_led_row(self, path, args):
        x_offset = args[0]
        y_offset = args[1]
        s = args[2:]
        bits = reduce(lambda x, y: x+y, [bitarray(b) for b in s], [])
        
        for b in range(len(bits)):
            bit = int(bits[b])
            self.grid_led_set(None, [x_offset+b, y_offset, bit])
    
    # FIXME: need len(args) check
    def grid_led_col(self, path, args):
        x_offset = args[0]
        y_offset = args[1]
        s = args[2:]
        bits = reduce(lambda x, y: x+y, [bitarray(b) for b in s], [])
        
        for b in range(len(bits)):
            bit = int(bits[b])
            self.grid_led_set(None, [x_offset, y_offset+b, bit])
    
    def grid_key(self, x, y, s):
        target = liblo.Address(self.app_host, self.app_port)
        liblo.send(target, "%s/grid/key" % self.prefix, x, y, s)

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
        
        self.xsize = xsize
        self.ysize = ysize
        self.buttons = [[gtk.Button() for y in range(ysize)] for x in range(xsize)]
        
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
        
        gobject.timeout_add(10, self.idle)
    
    def idle(self):
        self.s.poll()
        #import time
        #time.sleep(0.001)
        return True
    
    def button_clicked(self, b, x, y):
        print "clicked", b, x, y
        self.s.server.grid_key(x, y, 1)
    
    def light_button(self, x, y):
        if x >= self.xsize or y >= self.ysize: return
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#880000"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aa0000"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ff0000"))
    
    def unlight_button(self, x, y):
        if x >= self.xsize or y >= self.ysize: return
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#888888"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aaaaaa"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ffffff"))
    
    def do_delete_event(self, *args):
        self.s.close()
        gtk.main_quit()

gobject.type_register(MemeGui)

w = MemeGui(8080, 8, 8)
w.show_all()
gtk.main()

