#! /usr/bin/env python
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-

import gtk, gobject

from OSC import OSCClient, OSCServer, OSCMessage
import select, pybonjour
REGTYPE = "_monome-osc._udp"
NAME_FORMAT = "meme-%d"

def bitarray(b):
    return [b&1, b>>1&1, b>>2&1, b>>3&1, b>>4&1, b>>5&1, b>>6&1, b>>7&1]

def quick_message(host, port, path, *args):
    msg = OSCMessage(path)
    [msg.append(d) for d in args]
    client = OSCClient()
	client.sendto(msg, (host, port), timeout=0)

class Meme(OSCServer):
    def __init__(self, port, gui):
        OSCServer.__init__(self, ('localhost', port))
        self.app_port = 8000
        self.app_host = "localhost"
        self.prefix = "/monome"
        self.rotation = 0 # FIXME
        self.gui = gui
        
        self.register_syscallbacks()
        self.register_callbacks(self.prefix)
    
    def sys_port(self, addr, tags, data, client_address):
        self.app_port = data[0]
    
    def sys_host(self, addr, tags, data, client_address):
        self.app_host = data[0]
    
    def sys_prefix(self, addr, tags, data, client_address):
        prefix = data[0]
        self.unregister_callbacks(self.prefix)
        self.prefix = "/%s" % prefix.strip("/")
        self.register_callbacks(self.prefix)
    
    def sys_info(self, addr, tags, data, client_address):
        if len(data) == 2:
            host, port = data
        elif len(data) == 1:
            host, port = self.app_host, data[0]
        elif len(data) == 0:
            host, port = self.app_host, self.app_port
        else:
            return
        
        quick_message(host, port, "/sys/port", port)
        quick_message(host, port, "/sys/host", host)
        quick_message(host, port, "/sys/id", "meme")
        quick_message(host, port, "/sys/prefix", self.prefix)
        quick_message(host, port, "/sys/size", self.gui.xsize, self.gui.ysize)
    
    def unregister_callbacks(self, prefix):
        self.delMsgHandler("%s/grid/led/set" % prefix)
        self.delMsgHandler("%s/grid/led/map" % prefix)
        self.delMsgHandler("%s/grid/led/row" % prefix)
        self.delMsgHandler("%s/grid/led/col" % prefix)
        self.delMsgHandler("%s/grid/led/all" % prefix)
    
    def register_callbacks(self, prefix):
        self.addMsgHandler("%s/grid/led/set" % prefix, self.grid_led_set)
        self.addMsgHandler("%s/grid/led/map" % prefix, self.grid_led_map)
        self.addMsgHandler("%s/grid/led/row" % prefix, self.grid_led_row)
        self.addMsgHandler("%s/grid/led/col" % prefix, self.grid_led_col)
        self.addMsgHandler("%s/grid/led/all" % prefix, self.grid_led_all)

    def register_syscallbacks(self):
        self.addMsgHandler("/sys/port", self.sys_port)
        self.addMsgHandler("/sys/host", self.sys_host)
        self.addMsgHandler("/sys/prefix", self.sys_prefix)
        self.addMsgHandler("/sys/info", self.sys_info)

    def grid_led_set(self, addr, tags, data, client_address):
        print "led set", addr, data
        x, y, s = data
        if s == 1:
            self.gui.light_button(x, y)
        else:
            self.gui.unlight_button(x, y)
    
    def grid_led_map(self, addr, tags, data, client_address):
        x_offset = data[0]
        y_offset = data[1]
        s = data[2:]
        for i in range(len(s)):
            self.grid_led_row(None, None, [x_offset, y_offset+i, s[i]], None) # FIXME
    
    # FIXME: need len(args) check
    def grid_led_row(self, addr, tags, data, client_address):
        x_offset = data[0]
        y_offset = data[1]
        s = data[2:]
        bits = reduce(lambda x, y: x+y, [bitarray(b) for b in s], [])
        
        for b in range(len(bits)):
            bit = int(bits[b])
            self.grid_led_set(None, None, [x_offset+b, y_offset, bit], None) # FIXME
    
    # FIXME: need len(args) check
    def grid_led_col(self, addr, tags, data, client_address):
        x_offset = args[0]
        y_offset = args[1]
        s = args[2:]
        bits = reduce(lambda x, y: x+y, [bitarray(b) for b in s], [])
        
        for b in range(len(bits)):
            bit = int(bits[b])
            self.grid_led_set(None, None, [x_offset, y_offset+b, bit], None) # FIXME
    
    def grid_led_all(self, addr, tags, data, client_address):
        s = data[0]
        self.gui.led_all(s)
    
    def grid_key(self, x, y, s):
        msg = OSCMessage("%s/grid/key" % self.prefix)
        msg.append(x)
        msg.append(y)
        msg.append(s)
    	self.client.sendto(msg, (self.app_host, self.app_port), timeout=0)

class MemeGui(gtk.Window):
    def __init__(self, port, xsize, ysize):
        gtk.Window.__init__(self)

        self.meme = Meme(port, self)
        self.meme_service = pybonjour.DNSServiceRegister(name = NAME_FORMAT % port,
             regtype = REGTYPE,
             port = port,
             callBack = None)
        
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
        ready = select.select([self.meme_service, self.meme], [], [], 0)
        if self.meme_service in ready[0]:
            pybonjour.DNSServiceProcessResult(self.meme_service)
        if self.meme in ready[0]:
            self.meme.handle_request()
        return True
    
    def button_clicked(self, b, x, y):
        self.meme.grid_key(x, y, 1)
    
    def led_all(self, s):
        if s == 0:
            func = self.unlight_button
        else:
            func = self.light_button
        for x in range(self.xsize):
            for y in range(self.ysize):
                func(x, y)
    
    def light_button(self, x, y):
        if not x in range(self.xsize) or not y in range(self.ysize): return
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#880000"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aa0000"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ff0000"))
    
    def unlight_button(self, x, y):
        if not x in range(self.xsize) or not y in range(self.ysize): return
        b = self.buttons[x][y]
        b.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("#888888"))
        b.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#aaaaaa"))
        b.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color("#ffffff"))
    
    def do_delete_event(self, *args):
        self.meme.close()
        self.meme_service.close()
        gtk.main_quit()

gobject.type_register(MemeGui)

w = MemeGui(8081, 16, 16)
w.show_all()
gtk.main()

