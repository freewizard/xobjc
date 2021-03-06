#!/usr/bin/env python

"""
TODO:

- ATOMIC
- ViewDidUnload
- Readonly
- Work with more implementations etc. in one file and match name
- Create properties and synthesize in order the are defined in var block

CHANGELOG:

0.1 
- Initial release

0.2 (2009-09-04)
- Dealloc can contain custom data
- Adds missing dealloc correctly

0.3 (2009-09-11)
- viewDidUnload support

"""

import re
import os
import os.path
import shutil
import pprint
import datetime

rxh = re.compile("""
.*?
@interface .*? 
\{ 
(?P<varblock> .*?)
\}
(?P<properties> .*?)
@end
.*?
""", re.VERBOSE|re.M|re.DOTALL)

rxm = re.compile("""
.*?
\@implementation\s+[a-zA-Z0-9_]+
(?P<body> .*?)
\@end
""", re.VERBOSE|re.M|re.DOTALL)

rxdealloc = re.compile("""
\-\s*\(void\)\s*
	dealloc
	\s*
	\{
	(?P<deallocbody> .*?)	
	\[\s*super\s+dealloc\s*\]\s*\;\s*
	\}
""", re.VERBOSE|re.M|re.DOTALL)

rxrelease = re.compile("""
\[\s*[^\s]+\s+release\s*\]\s*\;\s*$
""", re.VERBOSE|re.M|re.DOTALL)

rxviewdidunload = re.compile("""
\-\s*\(void\)\s*
	viewDidUnload
	\s*
	\{
	(?P<viewdidunloadbody> [^\}]*?)		
	\}
""", re.VERBOSE|re.M|re.DOTALL)

rxunloadstuff = re.compile("""
\[\s*super\s+viewDidUnload\s*\]\s*\;
|
self\.[a-zA-Z0-9_]+ \s* \= \s* XNIL \s* \;
""", re.VERBOSE|re.M|re.DOTALL)

rxvars = re.compile("""
	(XCOPY | XASSIGN | XRETAIN | XATOMIC | XREADONLY | XIBOUTLET | IBOutlet)
	\s+
	([a-zA-Z0-9_][a-zA-Z0-9_\<\>]*)
	\s+
	((		
		\*?
		\s*
		[a-zA-Z0-9_]+
		\s*
		\,?			
		\s*
	)+)
	\;
""", re.VERBOSE|re.M|re.DOTALL)

rxproperties = re.compile("""
	\@property  
	
	\s*
	
	(
		\( 
		\s*
		(copy | assign | retain | atomic | nonatomic)
		\s*
		\,?
		\s*
		(copy | assign | retain | atomic | nonatomic)?
		\s*
		\)
	)?
	
	\s*
	
	([a-zA-Z0-9_][a-zA-Z0-9_\<\>]*)
	
	\s+
	
	((		
		\*?
		\s*
		[a-zA-Z0-9_]+
		\s*
		\,?			
		\s*
	)+)
	\;
	
""", re.VERBOSE|re.M|re.DOTALL)

rxsyn =  re.compile("""
	\@synthesize
	\s+
	\w+	   
	\s*
	\=?
	\s*
	\w*
	\;	
""", re.VERBOSE|re.M|re.DOTALL)

rxleadingunderscore = re.compile("(\s*\*?\s*)_(.+)")

class Module:
	
	def __init__(filename):
		self.base = filename[:filename.rfind(".")]
		self.h = self.base + '.h'
		self.m = self.baee = ".m"

def extractVariables(data):
	return [x.strip() for x in data.strip().split(",")]

def insertString(base, pos, new):
	return base[:pos] + new + base[pos:]

def analyze(hdata, mdata):
	
	# HEADER
	
	vars = dict()
	m = rxh.match(hdata)
	varblock = m.group("varblock").strip()
	properties = m.group("properties")	
	if varblock and properties:
		
		# Analyze variable definitions
		# print repr(varblock.strip())		
		for mv in rxvars.finditer(varblock):						
			mode, type_, names, names_ = mv.groups()
			# print mode, type_, extractVariables(names)
			for vname in extractVariables(names):
				vars[vname] = (mode.lower(), type_)	
		# pprint.pprint(vars)
				
		# Analyze property definitions
		if 0:
			print repr(properties.strip())
			for mp in rxproperties.finditer(properties):
				mode, mode1, mode2, type_, names, names_ = mp.groups()			
				for vname in extractVariables(names):
					if vname in vars:
						del vars[vname]
		else:
			properties = rxproperties.sub('', properties).lstrip()
				
		# Create missing properties
		# print
		# pprint.pprint(vars)
		block = []	
		for vname in sorted(vars.keys()):
			# print vname
			mode, type_ = vars[vname]
			vnamem = rxleadingunderscore.match(vname)
			if 1: #mode != 'iboutlet':   
				if vname.endswith('_'):
					vname = vname[:-1]
				elif vnamem:
					vname = vnamem.group(1) + vnamem.group(2)
				if mode == 'iboutlet':
					mode = 'retain'
				elif mode == 'xiboutlet':
					mode = "retain"
					type_ = "IBOutlet %s" % type_
				else:
					mode = mode[1:]				
				block.append("@property (nonatomic, %s) %s %s;" % (mode, type_, vname))
		block = "\n".join(block)		
		
		hdata = hdata[:m.start("properties")] + '\n\n' + block + '\n\n' + properties + hdata[m.end("properties"):]
		# print hdata
		
		# print "=" * 60
		 
		# MODULE
	
		# print mdata
		m = rxm.match(mdata)	
		#print m.groups()
	
		viewdidunload = []
		dealloc = []	   
		block = []	
	
		for vname in sorted(vars.keys()):
			# print vname
			mode, type_ = vars[vname]
			vname = vname.lstrip('*')
			pvname = vname
			if 1: # mode != 'iboutlet':  
				if vname.endswith('_'):
					pvname = vname[:-1]
					block.append("@synthesize %s = %s;" % (pvname, vname))
				elif vname.startswith('_'):
					pvname = vname[1:]
					block.append("@synthesize %s = %s;" % (pvname, vname))
				else:
					block.append("@synthesize %s;" % (vname))
			if mode not in ('xassign'):
				dealloc.append("	[%s release];" % vname)
			if mode.endswith('iboutlet'):
				viewdidunload.append("	self.%s = XNIL;" % pvname)
				
		body = rxsyn.sub('',  m.group("body")).strip()
		block = '\n\n' + "\n".join(block) + '\n\n'
				
		# dealloc
		md = rxdealloc.search(body)
		if md:
			deallocbody = rxrelease.sub('', md.group("deallocbody")).strip()	 
			if deallocbody:
				deallocbody = "	" + deallocbody + "\n\n"
			newdealloc =  "- (void)dealloc{\n" + deallocbody + "\n".join(dealloc) + "\n	[super dealloc];\n}" 
			body = rxdealloc.sub(newdealloc, body)
		else:
			newdealloc =  "- (void)dealloc{\n" + "\n".join(dealloc) + "\n	[super dealloc];\n}" 
			body += "\n\n" + newdealloc  

		# viewdidunload
		md = rxviewdidunload.search(body)
		if md:
			viewdidunloadbody = rxunloadstuff.sub('', md.group("viewdidunloadbody")).strip()	 
			if viewdidunloadbody:
				viewdidunloadbody = "\n	" + viewdidunloadbody + "\n\n"
			newviewdidunloadbody =  "- (void)viewDidUnload{\n	[super viewDidUnload];\n" + viewdidunloadbody + "\n".join(viewdidunload) + "\n}" 
			body = rxviewdidunload.sub(newviewdidunloadbody, body)
	   
		mdata = mdata[:m.start('body')] + block + body + '\n\n' + mdata[m.end('body'):] 
		
	return hdata, mdata

def modifyFiles(filename):
	# Calc filename
	base = os.path.normpath(os.path.abspath(filename))
	folder = os.path.dirname(base)
	filePart = os.path.basename(base)
	hfile = filename[:filename.rfind(".")] + '.h'
	mfile = filename[:filename.rfind(".")] + '.m'
	
	# Check files
	if not os.path.isfile(hfile):
		print "File %r does not exist" % hfile
		return
	if not os.path.isfile(mfile):
		print "File %r does not exist" % hfile
		return
	
	# Backup files
	backupFolder = os.path.join(folder, '.xobjc-backup', 'backup-' + datetime.datetime.today().strftime("%Y%m%d-%H%M%S"))
	os.makedirs(backupFolder)
	shutil.copyfile(hfile, os.path.join(backupFolder, filePart[:-2] + '.h'))
	shutil.copyfile(mfile, os.path.join(backupFolder, filePart[:-2] + '.m'))
	print "Created backup of files in %r" % backupFolder

	# Convert
	hdata, mdata = analyze(
		open(hfile).read(), 
		open(mfile).read())	
	open(hfile, 'w').write(hdata)
	open(mfile, 'w').write(mdata)
	print "Modified %r" % hfile
	print "Modified %r" % mfile
	
if __name__=="__main__":
	import sys
		
	# You can also place it into 'XCode User Scripts' but it does not relead the window yet
	try:
		filename = '%%%{PBXFilePath}%%%'
	except:
		filename = ''
	
	if filename and (not filename.startswith('%')):
		modifyFiles(filename)

		# Trick to reload files in XCode
		import subprocess		
		subprocess.call(['osascript', '-e', 'activate application "Finder"'])
		subprocess.call(['osascript', '-e', 'activate application "XCode"'])

	else:
		if len(sys.argv)!=2:
			print "Usage: xobjc.py [filename]"
		else:
			modifyFiles(sys.argv[1])
