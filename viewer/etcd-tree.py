#!/usr/bin/python3
# -*- coding: utf8 -*-

from __future__ import division
from gi.repository import Gtk
from gi.repository import GObject, GLib
import os

import etcd
from dabroker.util import attrdict

class DEL: pass

et = etcd.Client()

APPNAME="etcd-tree"

class AssocUI(object):
	tree_index = None

	def __init__(self):
		self.guid2acct = {}
		#self._init_acctcache()

		#gnome.init(APPNAME, APPVERSION)
		from pkg_resources import Requirement, resource_filename
		filename = resource_filename(Requirement.parse("moatree"),os.path.join("viewer",APPNAME+".glade"))

		self.widgets = Gtk.Builder()
		self.widgets.add_from_file(filename)

		d = AssocUI.__dict__.copy()
		for k in d.keys():
			d[k] = getattr(self,k)
		self.widgets.connect_signals(d)
		self.init_tree()
		#self._get_src_accts()
		self.fill_tree()
		#self.get_filters()
		#self.enable_stuff()

		self['main'].show_all()
		self.listen_tree(self.tree_index+1)

	def tree_sort(self,col,colnr):
		v = self['dest_view']
		m = v.get_model()
		
		if m.get_sort_column_id() == colnr:
			pass # revert?
		else:
			v.get_column(colnr).set_sort_column_id(0)
			m.set_sort_column_id(colnr,Gtk.SortType.ASCENDING)

	def init_tree(self):
		"""Setup the tree view for the status view"""
		v = self['dest_view']
		s = v.get_selection()
		s.set_mode(Gtk.SelectionMode.SINGLE)

		m = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
		# name, value
		v.set_model(m)
		v.set_headers_visible(True)

		c = v.get_column(1)
		if c: v.remove_column(c)
		c = v.get_column(0)
		if c: v.remove_column(c)

		r = Gtk.CellRendererText()
		column = Gtk.TreeViewColumn('Name',r,text=0)
		column.set_sizing (Gtk.TreeViewColumnSizing.FIXED)
		column.set_clickable(True)
		column.connect("clicked",self.tree_sort,0)
		v.append_column(column)
		cell = Gtk.CellRendererText()
		column.pack_start(cell, True)

		column = Gtk.TreeViewColumn('Value',r,text=1)
		column.set_sizing (Gtk.TreeViewColumnSizing.FIXED)
		column.set_clickable(True)
		column.connect("clicked",self.tree_sort,1)
		v.append_column(column)
		cell = Gtk.CellRendererText()
		column.pack_start(cell, True)

	def __getitem__(self,name):
		"Shortcut."
		return self.widgets.get_object(name)

### The basic entry tree

	def tree_node(self, name, value=None, node=None):
		"""Set a single node, creating subdirectories where necessary and keeping expansion state"""
		v = self['dest_view']
		m = v.get_model()
		onode = oname = None
		expanded = True

		if name.startswith('/'):
			node = self.tree
			name = name[1:]
		elif node is None:
			node = self.tree
		for n in name.split('/'):
			e = node.get(n,None)
			if e is None:
				if value is DEL: return
				p = m.append(node.get('_node',None),row=[n,'-dir-'])
				node[n] = e = {'_node':p}
				if expanded and node and '_node' in node:
					v.expand_row(m.get_path(node['_node']),False)
			else:
				expanded = v.row_expanded(m.get_path(e['_node']))

			onode = node
			oname = n
			node = e
		if value is DEL:
			m.remove(node['_node'])
			if onode: del onode[oname]

		elif value is not None:
			node['_value'] = value
			m.set_value(node['_node'],1,value)

	def fill_tree(self):
		"""load the initial view"""

		# TODO: do this incrementally?
		v = self['dest_view']
		m = v.get_model()
		m.clear()
		self.tree = attrdict()

		res = et.read('/',recursive=True)

		def fill_dest(nr,it,d):
			na = nr['key'][nr['key'].rindex('/')+1:]
			v = nr.get('value','-dir-')
			p = m.append(it,row=[na,v])
			#print("add",na,v,str(m.get_path(p)))
			d[na] = nd = {'_node':p, '_value':v}
			if nr.get('dir',False):
				for r in nr['nodes']:
					fill_dest(r,p,nd)
			
		for r in res._children:
			fill_dest(r,None,self.tree)
		self.tree_index = res.etcd_index

	def _get_tree(self,pipe,start):
		"""Background process which polls etcd"""
		et = etcd.Client()
		for r in et.eternal_watch("/", index=start, recursive=True):
			pipe.send(r)

	def _io_tree(self, fd,cond, pipe):
		"""Reader for the background connection to etcd"""
		res = pipe.recv()
		print(res)
		self.tree_node(res.key,DEL if res.action == "delete" else res.value)
		return True

	def listen_tree(self,start=None):
		"""Start a listener for etcd events"""
		from multiprocessing import Process, Pipe
		parent_conn, child_conn = Pipe()
		self.tree_listener = Process(target=self._get_tree, args=(child_conn,start))
		self.tree_listener.start()
		GLib.io_add_watch(parent_conn.fileno(), GLib.IO_IN, self._io_tree,parent_conn)
	
	def cleanup(self):
		self.tree_listener.terminate()
		self.tree_listener.join()
		
###	EVENTS

	def on_main_destroy(self,window):
		# main window goes away
		Gtk.main_quit()

	def on_main_delete_event(self,window,event):
		# True if the window should not be deleted
		return False

	def on_quit_button_clicked(self,x):
		Gtk.main_quit()

import sys
if __name__ == "__main__":
	widgets = AssocUI()

	def icb(*a):
		print("RECV",*a)
	#def ti():
	#	from signal import signal,SIGINT
	#	signal(SIGINT,Gtk.main_quit)

	Gtk.main()
	print("done")
	widgets.cleanup()

# END #
