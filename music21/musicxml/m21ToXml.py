# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:         musicxml/m21ToXml.py
# Purpose:      Translate from music21 objects to musicxml representation
#
# Authors:      Christopher Ariza
#               Michael Scott Cuthbert
#
# Copyright:    Copyright © 2010-2012, 2015 Michael Scott Cuthbert and the music21 Project
# License:      LGPL or BSD, see license.txt
#-------------------------------------------------------------------------------
'''
Converters for music21 objects to musicxml.

Does not handle the entire string architecture, that's what m21ToString is for.

Assumes that the outermost object is a score.
'''
from __future__ import print_function, division

from collections import OrderedDict
import unittest
import datetime
from music21.ext import webcolors, six

if six.PY3:
    import xml.etree.ElementTree as ET  # @UnusedImport
    from xml.etree.ElementTree import Element, SubElement # @UnusedImport

else:
    try:
        import xml.etree.cElementTree as ET
        from xml.etree.cElementTree import Element, SubElement
 
    except ImportError:
        import xml.etree.ElementTree as ET # @UnusedImport
        from xml.etree.ElementTree import Element, SubElement


# modules that import this include converter.py.
# thus, cannot import these here
from music21 import common
from music21 import defaults
from music21 import exceptions21

from music21 import bar
from music21 import key
from music21 import metadata
from music21 import note
from music21 import meter
from music21 import spanner
from music21 import stream

from music21.musicxml import xmlObjects

from music21 import environment
_MOD = "musicxml.m21ToXml"
environLocal = environment.Environment(_MOD)

#-------------------------------------------------------------------------------
class ToMxObjectsException(exceptions21.Music21Exception):
    pass
class NoteheadException(ToMxObjectsException):
    pass

def dump(xmlEl):
    r'''
    wrapper around xml.etree.ElementTree as ET that returns a string
    in every case, whether Py2 or Py3...

    >>> from music21.musicxml.m21ToXml import Element
    >>> e = Element('accidental')
    >>> musicxml.m21ToXml.dump(e)
    <accidental />
    
    >>> e.text = u'∆'
    >>> e.text == u'∆'
    True
    >>> musicxml.m21ToXml.dump(e)
    <accidental>...</accidental>

    Output differs in Python2 vs 3.
    '''
    if six.PY2:
        print(ET.tostring(xmlEl))
    else:
        print(ET.tostring(xmlEl, encoding='unicode'))

def typeToMusicXMLType(value):
    '''Convert a music21 type to a MusicXML type.
    
    >>> musicxml.m21ToXml.typeToMusicXMLType('longa')
    'long'
    >>> musicxml.m21ToXml.typeToMusicXMLType('quarter')
    'quarter'
    '''
    # MusicXML uses long instead of longa
    if value == 'longa': 
        return 'long'
    elif value == '2048th':
        raise ToMxObjectsException('Cannot convert "2048th" duration to MusicXML (too short).')
    else:
        return value

def accidentalToMx(a):
    '''
    >>> a = pitch.Accidental()
    >>> a.set('half-sharp')
    >>> a.alter == .5
    True
    >>> mxAccidental = musicxml.m21ToXml.accidentalToMx(a)
    >>> musicxml.m21ToXml.dump(mxAccidental)
    <accidental>quarter-sharp</accidental>

    >>> a.set('one-and-a-half-sharp')
    >>> mxAccidental = musicxml.m21ToXml.accidentalToMx(a)
    >>> musicxml.m21ToXml.dump(mxAccidental)
    <accidental>three-quarters-sharp</accidental>

    >>> a.set('half-flat')
    >>> mxAccidental = musicxml.m21ToXml.accidentalToMx(a)
    >>> musicxml.m21ToXml.dump(mxAccidental)
    <accidental>quarter-flat</accidental>

    >>> a.set('one-and-a-half-flat')
    >>> mxAccidental = musicxml.m21ToXml.accidentalToMx(a)
    >>> musicxml.m21ToXml.dump(mxAccidental)
    <accidental>three-quarters-flat</accidental>

    '''
    if a.name == "half-sharp": 
        mxName = "quarter-sharp"
    elif a.name == "one-and-a-half-sharp": 
        mxName = "three-quarters-sharp"
    elif a.name == "half-flat": 
        mxName = "quarter-flat"
    elif a.name == "one-and-a-half-flat": 
        mxName = "three-quarters-flat"
    else: # all others are the same
        mxName = a.name

    mxAccidental = Element('accidental')
    # need to remove display in this case and return None
    #         if self.displayStatus == False:
    #             pass
    mxAccidental.text = mxName
    return mxAccidental
    

def normalizeColor(color):
    '''
    Normalize a css3 name to hex or leave it alone...
    
    >>> musicxml.m21ToXml.normalizeColor('')
    ''
    >>> musicxml.m21ToXml.normalizeColor('red')
    '#FF0000'
    >>> musicxml.m21ToXml.normalizeColor('#00ff00')
    '#00FF00'
    '''
    if color in (None, ''):
        return color
    if '#' not in color:
        return (webcolors.css3_names_to_hex[color]).upper()
    else:
        return color.upper()


def _setTagTextFromAttribute(m21El, xmlEl, tag, attributeName=None, 
                             transform=None, forceEmpty=False):
    '''
    If m21El has an attribute called attributeName, create a new SubElement
    for xmlEl and set its text to the value of the m21El attribute.
    
    Pass a function or lambda function as transform to transform the
    value before setting it.  String transformation is assumed.
    
    Returns the subelement
    
    Will not create an empty element unless forceEmpty is True
    
    >>> from music21.musicxml.m21ToXml import Element
    >>> e = Element('accidental')

    >>> seta = musicxml.m21ToXml._setTagTextFromAttribute
    >>> acc = pitch.Accidental()
    >>> acc.alter = -2
    >>> subEl = seta(acc, e, 'alter')
    >>> subEl.text
    '-2'
    >>> subEl in e
    True
    >>> musicxml.m21ToXml.dump(e)
    <accidental><alter>-2</alter></accidental>

    add a transform

    >>> subEl = seta(acc, e, 'alter', transform=float)
    >>> subEl.text
    '-2.0'

    '''
    if attributeName is None:
        attributeName = common.hyphenToCamelCase(tag)

    try:
        value = getattr(m21El, attributeName)
    except AttributeError:
        return None

    if transform is not None:
        value = transform(value)

    if value in (None, "") and forceEmpty is not True:
        return None
    
    subElement = SubElement(xmlEl, tag)
    
    if value not in (None, ""):
        subElement.text = str(value)

    return subElement
    
def _setAttributeFromAttribute(m21El, xmlEl, xmlAttributeName, attributeName=None, transform=None):
    '''
    If m21El has a at least one element of tag==tag with some text. If
    it does, set the attribute either with the same name (with "foo-bar" changed to
    "fooBar") or with attributeName to the text contents.
    
    Pass a function or lambda function as transform to transform the value before setting it
    
    >>> from xml.etree.ElementTree import fromstring as El

    >>> e = El('<page-layout/>')

    >>> setb = musicxml.m21ToXml._setAttributeFromAttribute
    >>> pl = layout.PageLayout()
    >>> pl.pageNumber = 4
    >>> pl.isNew = True
    
    >>> setb(pl, e, 'page-number')
    >>> e.get('page-number')
    '4'
    >>> musicxml.m21ToXml.dump(e)
    <page-layout page-number="4" />

    >>> setb(pl, e, 'new-page', 'isNew')
    >>> e.get('new-page')
    'True'


    Transform the isNew value to 'yes'.

    >>> convBool = musicxml.xmlObjects.booleanToYesNo
    >>> setb(pl, e, 'new-page', 'isNew', transform=convBool)
    >>> e.get('new-page')
    'yes'
    '''
    if attributeName is None:
        attributeName = common.hyphenToCamelCase(xmlAttributeName)

    value = getattr(m21El, attributeName)
    if value is None:
        return

    if transform is not None:
        value = transform(value)

    xmlEl.set(xmlAttributeName, str(value))



class XMLExporterBase(object):
    '''
    contains functions that could be called
    at multiple levels of exporting (Score, Part, Measure).
    '''
    
    def __init__(self):
        pass
    
    def dump(self, obj):
        dump(obj)
    
    def setPosition(self, m21Object, mxObject):
        if hasattr(m21Object, 'xPosition') and m21Object.xPosition is not None:
            mxObject.set('default-x', m21Object.xPosition)
        # TODO: attr: default-y, relative-x, relative-y
        # TODO: standardize "positionVertical, etc.

    def pageLayoutToXmlPrint(self, pageLayout, mxPrintIn=None):
        '''
        Given a PageLayout object, set object data for <print> 
    
        >>> pl = layout.PageLayout()
        >>> pl.pageHeight = 4000
        >>> pl.isNew = True
        >>> pl.rightMargin = 30.25
        >>> pl.leftMargin = 20
        >>> pl.pageNumber = 5

        >>> XPBase = musicxml.m21ToXml.XMLExporterBase()
        >>> mxPrint = XPBase.pageLayoutToXmlPrint(pl)
        >>> XPBase.dump(mxPrint)
        <print new-page="yes" page-number="5"><page-layout><page-height>4000</page-height><page-margins><left-margin>20</left-margin><right-margin>30.25</right-margin></page-margins></page-layout></print>


        >>> MP = musicxml.xmlToM21.MeasureParser()
        >>> pl2 = MP.xmlPrintToPageLayout(mxPrint)
        >>> pl2.isNew
        True
        >>> pl2.rightMargin
        30.25
        >>> pl2.leftMargin
        20
        >>> pl2.pageNumber
        5    
        >>> pl2.pageHeight
        4000
        '''
        if mxPrintIn is None:
            mxPrint = Element('print')
        else:
            mxPrint = mxPrintIn
        
        setb = _setAttributeFromAttribute
        setb(pageLayout, mxPrint, 'new-page', 'isNew', transform=xmlObjects.booleanToYesNo)
        setb(pageLayout, mxPrint, 'page-number')
    
        mxPageLayout = self.pageLayoutToXmlPageLayout(pageLayout)
        if len(mxPageLayout) > 0:
            mxPrint.append(mxPageLayout)
    
        if mxPrintIn is None:
            return mxPrint
        
    def pageLayoutToXmlPageLayout(self, pageLayout, mxPageLayoutIn=None):
        '''
        get a <page-layout> element from a PageLayout
        
        Called out from pageLayoutToXmlPrint because it
        is also used in the <defaults> tag
        '''
        if mxPageLayoutIn is None:
            mxPageLayout = Element('page-layout')
        else:
            mxPageLayout = mxPageLayoutIn

        seta = _setTagTextFromAttribute
        
        seta(pageLayout, mxPageLayout, 'page-height')
        seta(pageLayout, mxPageLayout, 'page-width')
        
        #TODO -- record even, odd, both margins
        mxPageMargins = Element('page-margins')
        for direction in ('left', 'right', 'top', 'bottom'):
            seta(pageLayout, mxPageMargins, direction + '-margin')
        if len(mxPageMargins) > 0:
            mxPageLayout.append(mxPageMargins)

        if mxPageLayoutIn is None:
            return mxPageLayout


    def systemLayoutToXmlPrint(self, systemLayout, mxPrintIn=None):
        '''
        Given a SystemLayout tag, set a <print> tag
        
        >>> sl = layout.SystemLayout()
        >>> sl.distance = 55
        >>> sl.isNew = True
        >>> sl.rightMargin = 30.25
        >>> sl.leftMargin = 20

        >>> XPBase = musicxml.m21ToXml.XMLExporterBase()
        >>> mxPrint = XPBase.systemLayoutToXmlPrint(sl)
        >>> XPBase.dump(mxPrint)
        <print new-system="yes"><system-layout><system-margins><left-margin>20</left-margin><right-margin>30.25</right-margin></system-margins><system-distance>55</system-distance></system-layout></print>

        Test return conversion
        
        >>> MP = musicxml.xmlToM21.MeasureParser()
        >>> sl2 = MP.xmlPrintToSystemLayout(mxPrint)
        >>> sl2.isNew
        True
        >>> sl2.rightMargin
        30.25
        >>> sl2.leftMargin
        20
        >>> sl2.distance
        55
        '''
        if mxPrintIn is None:
            mxPrint = Element('print')
        else:
            mxPrint = mxPrintIn
    
        setb = _setAttributeFromAttribute
        setb(systemLayout, mxPrint, 'new-system', 'isNew', transform=xmlObjects.booleanToYesNo)

        mxSystemLayout = Element('system-layout')
        self.systemLayoutToXmlSystemLayout(systemLayout, mxSystemLayout)
        if len(mxSystemLayout) > 0:
            mxPrint.append(mxSystemLayout)
    
        if mxPrintIn is None:
            return mxPrint


    def systemLayoutToXmlSystemLayout(self, systemLayout, mxSystemLayoutIn=None):
        '''
        get given a SystemLayout object configure <system-layout> or <print>
        
        Called out from xmlPrintToSystemLayout because it
        is also used in the <defaults> tag

        >>> sl = layout.SystemLayout()
        >>> sl.distance = 40.0
        >>> sl.topDistance = 70.0
        >>> XPBase = musicxml.m21ToXml.XMLExporterBase()
        >>> mxSl = XPBase.systemLayoutToXmlSystemLayout(sl)
        >>> XPBase.dump(mxSl)
        <system-layout><system-distance>40.0</system-distance><top-system-distance>70.0</top-system-distance></system-layout>

        >>> sl = layout.SystemLayout()
        >>> sl.leftMargin = 30.0
        >>> mxSl = XPBase.systemLayoutToXmlSystemLayout(sl)
        >>> XPBase.dump(mxSl)
        <system-layout><system-margins><left-margin>30.0</left-margin></system-margins></system-layout>
        '''
        if mxSystemLayoutIn is None:
            mxSystemLayout = Element('system-layout')
        else:
            mxSystemLayout = mxSystemLayoutIn
    
        seta = _setTagTextFromAttribute
        
        #TODO -- record even, odd, both margins
        mxSystemMargins = Element('system-margins')
        for direction in ('top', 'bottom', 'left', 'right'):
            seta(systemLayout, mxSystemMargins, direction + '-margin')
        if len(mxSystemMargins) > 0:
            mxSystemLayout.append(mxSystemMargins)
                
        seta(systemLayout, mxSystemLayout, 'system-distance', 'distance')
        seta(systemLayout, mxSystemLayout, 'top-system-distance', 'topDistance')
        
        # TODO: system-dividers

        if mxSystemLayoutIn is None:
            return mxSystemLayout

    def staffLayoutToXmlStaffLayout(self, staffLayout, mxStaffLayoutIn=None):
        '''
        get a <staff-layout> tag from a StaffLayout object
        
        In music21, the <staff-layout> and <staff-details> are
        intertwined in a StaffLayout object.
        
        >>> sl = layout.StaffLayout()
        >>> sl.distance = 40.0
        >>> sl.staffNumber = 1
        >>> XPBase = musicxml.m21ToXml.XMLExporterBase()
        >>> mxSl = XPBase.staffLayoutToXmlStaffLayout(sl)
        >>> XPBase.dump(mxSl)
        <staff-layout number="1"><staff-distance>40.0</staff-distance></staff-layout>
        '''
        if mxStaffLayoutIn is None:
            mxStaffLayout = Element('staff-layout')
        else:
            mxStaffLayout = mxStaffLayoutIn
        seta = _setTagTextFromAttribute
        setb = _setAttributeFromAttribute
        
        seta(staffLayout, mxStaffLayout, 'staff-distance', 'distance')
        #ET.dump(mxStaffLayout)
        setb(staffLayout, mxStaffLayout, 'number', 'staffNumber')

        if mxStaffLayoutIn is None:
            return mxStaffLayout

#----------

class ScoreExporter(XMLExporterBase):
    '''
    Convert a Score (or outer stream with .parts) into
    a musicxml Element.
    '''
    def __init__(self, score=None):
        super(ScoreExporter, self).__init__()
        if score is None:
            # should not be done this way.
            self.stream = stream.Score()
        else:
            self.stream = score
        
        self.musicxmlVersion = "3.0"
        self.xmlRoot = Element('score-partwise')
        self.mxIdentification = None
        
        self.scoreMetadata = None
        
        self.spannerBundle = None
        self.meterStream = None
        self.scoreLayouts = None
        self.firstScoreLayout = None
        self.textBoxes = None
        self.highestTime = 0.0
        
        self.refStreamOrTimeRange = [0.0, self.highestTime]

        self.partExporterList = []

        self.instrumentList = []
        self.midiChannelList = []
        
        self.parts = []

    def parse(self):
        '''
        the main function to call.
        
        If self.stream is empty, call self.emptyObject().  Otherwise,
        
        set scorePreliminaries(), call parsePartlikeScore or parseFlatScore, then postPartProcess(),
        clean up circular references for garbage collection, and returns the <score-partwise>
        object.
        
        >>> b = corpus.parse('bwv66.6')
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        >>> mxScore = SX.parse()
        >>> SX.dump(mxScore)
        <score-partwise>...</score-partwise>
        '''
        s = self.stream
        if len(s) == 0:
            return self.emptyObject()

        self.scorePreliminaries()    

        if s.hasPartLikeStreams():
            self.parsePartlikeScore()
        else:
            self.parseFlatScore()
            
        self.postPartProcess()
        
        # clean up for circular references.
        self.partExporterList.clear()
        
        return self.xmlRoot


    def emptyObject(self):
        '''
        Creates a cheeky "This Page Intentionally Left Blank" for a blank score
        
        >>> emptySX = musicxml.m21ToXml.ScoreExporter()
        >>> mxScore = emptySX.parse() # will call emptyObject
        >>> emptySX.dump(mxScore)
        <score-partwise><work><work-title>This Page Intentionally Left Blank</work-title></work>...<note><rest /><duration>40320</duration><type>whole</type></note></measure></part></score-partwise>
        '''
        out = stream.Stream()
        p = stream.Part()
        m = stream.Measure()
        r = note.Rest(quarterLength=4)
        m.append(r)
        p.append(m)
        out.append(p)
        # return the processing of this Stream
        md = metadata.Metadata(title='This Page Intentionally Left Blank')
        out.insert(0, md)
        # recursive call to this non-empty stream
        self.stream = out
        return self.parse()
        
        
    def scorePreliminaries(self):
        '''
        Populate the exporter object with
        `meterStream`, `scoreLayouts`, `spannerBundle`, and `textBoxes`
        
        >>> emptySX = musicxml.m21ToXml.ScoreExporter()
        >>> emptySX.scorePreliminaries() # will call emptyObject
        >>> len(emptySX.textBoxes)
        0
        >>> emptySX.spannerBundle
        <music21.spanner.SpannerBundle of size 0>

        '''
        self.setScoreLayouts()
        self.setMeterStream()
        self.setPartsAndRefStream()
        # get all text boxes
        self.textBoxes = self.stream.flat.getElementsByClass('TextBox')
    
        # we need independent sub-stream elements to shift in presentation
        self.highestTime = 0.0 # redundant, but set here.

        if self.spannerBundle is None:
            self.spannerBundle = self.stream.spannerBundle

    def setPartsAndRefStream(self):
        '''
        Transfers the offset of the inner stream to elements and sets self.highestTime
        
        >>> b = corpus.parse('bwv66.6')
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        >>> SX.highestTime
        0.0
        >>> SX.setPartsAndRefStream()
        >>> SX.highestTime
        36.0
        >>> SX.refStreamOrTimeRange
        [0.0, 36.0]
        >>> len(SX.parts)
        4
        '''
        s = self.stream
        #environLocal.printDebug('streamToMx(): interpreting multipart')
        streamOfStreams = s.getElementsByClass('Stream')
        for innerStream in streamOfStreams:
            # may need to copy element here
            # apply this streams offset to elements
            innerStream.transferOffsetToElements()
            ht = innerStream.highestTime
            if ht > self.highestTime:
                self.highestTime = ht
        self.refStreamOrTimeRange = [0.0, self.highestTime]
        self.parts = streamOfStreams

    def setMeterStream(self):
        '''
        sets `self.meterStream` or uses a default.
        
        Used in makeNotation in Part later.
        
        >>> b = corpus.parse('bwv66.6')
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        >>> SX.setMeterStream()
        >>> SX.meterStream
        <music21.stream.Score 0x...>
        >>> len(SX.meterStream)
        4
        >>> SX.meterStream[0]
        <music21.meter.TimeSignature 4/4>
        '''
        s = self.stream
        # search context probably should always be True here
        # to search container first, we need a non-flat version
        # searching a flattened version, we will get contained and non-container
        # this meter  stream is passed to makeNotation()
        meterStream = s.getTimeSignatures(searchContext=False,
                        sortByCreationTime=False, returnDefault=False)
        #environLocal.printDebug(['streamToMx: post meterStream search', meterStream, meterStream[0]])
        if len(meterStream) == 0:
            # note: this will return a default if no meters are found
            meterStream = s.flat.getTimeSignatures(searchContext=False,
                        sortByCreationTime=True, returnDefault=True)
        self.meterStream = meterStream

        
    def setScoreLayouts(self):
        '''
        sets `self.scoreLayouts` and `self.firstScoreLayout`

        >>> b = corpus.parse('schoenberg/opus19', 2)
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        >>> SX.setScoreLayouts()
        >>> SX.scoreLayouts
        <music21.stream.Score 0x...>
        >>> len(SX.scoreLayouts)
        1
        >>> SX.firstScoreLayout
        <music21.layout.ScoreLayout>
        '''
        s = self.stream
        scoreLayouts = s.getElementsByClass('ScoreLayout')
        if len(scoreLayouts) > 0:
            scoreLayout = scoreLayouts[0]
        else:
            scoreLayout = None
        self.scoreLayouts = scoreLayouts
        self.firstScoreLayout = scoreLayout
    
        
    def parsePartlikeScore(self):
        '''
        called by .parse() if the score has individual parts.
        
        Calls makeRests() for the part, then creates a PartExporter for each part,
        and runs .parse() on that part.  appends the PartExporter to self.partExporterList()
        '''
        # would like to do something like this but cannot
        # replace object inside of the stream
        for innerStream in self.parts:
            innerStream.makeRests(self.refStreamOrTimeRange, inPlace=True)

        count = 0
        for innerStream in self.parts:
            count += 1
            if count > len(self.parts):
                raise ToMxObjectsException('infinite stream encountered')

            pp = PartExporter(innerStream, parent=self)
            pp.parse()
            self.partExporterList.append(pp)
    
    def parseFlatScore(self):
        '''
        creates a single PartExporter for this Stream and parses it.
        
        Note that the Score does not need to be totally flat, it just cannot have Parts inside it;
        measures are fine.
        
        >>> c = converter.parse('tinyNotation: 3/4 c2. d e')
        >>> SX = musicxml.m21ToXml.ScoreExporter(c)
        >>> SX.parseFlatScore()
        >>> len(SX.partExporterList)
        1
        >>> SX.partExporterList[0]
        <music21.musicxml.m21ToXml.PartExporter object at 0x...>
        >>> SX.dump(SX.partExporterList[0].xmlRoot)
        <part id="..."><measure number="1">...</measure></part>
        >>> SX.partExporterList.clear() # for garbage collection
        '''
        s = self.stream
        pp = PartExporter(s, parent=self)
        pp.parse()
        self.partExporterList.append(pp)
    

    def postPartProcess(self):
        '''
        calls .setScoreHeader() then appends each PartExporter's xmlRoot from
        self.partExporterList to self.xmlRoot
        
        Called automatically by .parse()
        '''
        self.setScoreHeader()
        for pex in self.partExporterList:
            self.xmlRoot.append(pex.xmlRoot)


    def setScoreHeader(self):
        '''
        Sets the group score-header in <score-partwise>.  Note that score-header is not
        a separate tag, but just a way of crouping things from the tag.
        
        runs `setTitles()`, `setIdentification()`, `setDefaults()`, changes textBoxes
        to `<credit>` and does the major task of setting up the part-list with `setPartList()`
        
        '''
        s = self.stream
        # create score and part list
        # set some score header information from metadata
        if s.metadata != None:
            self.scoreMetadata = s.metadata
    
        self.setTitles()
        self.setIdentification()
        self.setDefaults()
        # add text boxes as Credits
        for tb in self.textBoxes: # a stream of text boxes
            self.xmlRoot.append(self.textBoxToXmlCredit(tb))
    
        # the hard one...
        self.setPartList()
    
    def textBoxToXmlCredit(self, textBox):
        '''
        Convert a music21 TextBox to a MusicXML Credit.
        
        >>> tb = text.TextBox('testing')
        >>> tb.positionVertical = 500
        >>> tb.positionHorizontal = 300
        >>> tb.page = 3
        >>> SX = musicxml.m21ToXml.ScoreExporter()
        >>> mxCredit = SX.textBoxToXmlCredit(tb)
        >>> SX.dump(mxCredit)
        <credit page="3"><credit-words default-x="300" default-y="500" halign="center" valign="top">testing</credit-words></credit>
        
        Default of page 1:
        
        >>> tb = text.TextBox('testing')
        >>> tb.page
        1
        >>> mxCredit = SX.textBoxToXmlCredit(tb)
        >>> SX.dump(mxCredit)
        <credit page="1">...</credit>
        '''
        # use line carriages to separate messages
        mxCredit = Element('credit')
        # TODO: credit-type
        # TODO: link
        # TODO: bookmark
        # TODO: credit-image
        
        if textBox.page is not None:
            mxCredit.set('page', str(textBox.page))
        else:
            mxCredit.set('page', '1')
        
        # add all credit words to components
        count = 0
    
        for l in textBox.content.split('\n'):
            cw = Element('credit-words')
            cw.text = l
            # TODO: link/bookmark in credit-words
            if count == 0: # on first, configure properties         
                if textBox.positionHorizontal is not None:
                    cw.set('default-x', str(textBox.positionHorizontal))
                if textBox.positionVertical is not None:
                    cw.set('default-y', str(textBox.positionVertical))
                if textBox.justify is not None:
                    cw.set('justify', str(textBox.justify))
                if textBox.style is not None:
                    cw.set('font-style', str(textBox.style))
                if textBox.weight is not None:
                    cw.set('font-weight', str(textBox.weight))
                if textBox.size is not None:
                    cw.set('font-size', str(textBox.size))
#                else:
#                    cw.set('font-size', '12')
                if textBox.alignVertical is not None:
                    cw.set('valign', str(textBox.alignVertical))
                if textBox.alignHorizontal is not None:
                    cw.set('halign', str(textBox.alignHorizontal))
            mxCredit.append(cw)
            count += 1
        return mxCredit
    
    def setDefaults(self):
        '''
        Retuns a default object from self.firstScoreLayout or a very simple one if none exists.
        
        Simple:
        
        >>> SX = musicxml.m21ToXml.ScoreExporter()
        >>> mxDefaults = SX.setDefaults()
        >>> SX.dump(mxDefaults)
        <defaults><scaling><millimeters>7</millimeters><tenths>40</tenths></scaling></defaults>

        These numbers come from the `defaults` module:
        
        >>> defaults.scalingMillimeters
        7
        >>> defaults.scalingTenths
        40
        
        More complex:
        
        >>> s = corpus.parse('schoenberg/opus19', 2)
        >>> SX = musicxml.m21ToXml.ScoreExporter(s)
        >>> SX.setScoreLayouts() # necessary to call before .setDefaults()
        >>> mxDefaults = SX.setDefaults()
        >>> mxDefaults.tag
        'defaults'
        >>> mxScaling = mxDefaults.find('scaling')
        >>> SX.dump(mxScaling)
        <scaling><millimeters>6.1472</millimeters><tenths>40</tenths></scaling>
        >>> mxPageLayout = mxDefaults.find('page-layout')
        >>> SX.dump(mxPageLayout)
        <page-layout><page-height>1818</page-height><page-width>1405</page-width><page-margins>...
        >>> mxPageMargins = mxPageLayout.find('page-margins')
        >>> SX.dump(mxPageMargins)
        <page-margins><left-margin>83</left-margin><right-margin>83</right-margin><top-margin>103</top-margin><bottom-margin>103</bottom-margin></page-margins>
        >>> mxSystemLayout = mxDefaults.find('system-layout')
        >>> SX.dump(mxSystemLayout)
        <system-layout><system-margins>...</system-margins><system-distance>121</system-distance><top-system-distance>70</top-system-distance></system-layout>
        >>> mxStaffLayoutList = mxDefaults.findall('staff-layout')
        >>> len(mxStaffLayoutList)
        1
        >>> SX.dump(mxStaffLayoutList[0])
        <staff-layout><staff-distance>98</staff-distance></staff-layout>
        '''
        
        # get score defaults if any:
        if self.firstScoreLayout is None:
            from music21 import layout
            scoreLayout = layout.ScoreLayout()
            scoreLayout.scalingMillimeters = defaults.scalingMillimeters
            scoreLayout.scalingTenths = defaults.scalingTenths
        else:
            scoreLayout = self.firstScoreLayout

        mxDefaults = SubElement(self.xmlRoot, 'defaults')    
        if scoreLayout.scalingMillimeters is not None or scoreLayout.scalingTenths is not None:
            mxScaling = SubElement(mxDefaults, 'scaling')
            mxMillimeters = SubElement(mxScaling, 'millimeters')
            mxMillimeters.text = str(scoreLayout.scalingMillimeters)
            mxTenths = SubElement(mxScaling, 'tenths')
            mxTenths.text = str(scoreLayout.scalingTenths)

        if scoreLayout.pageLayout is not None:
            mxPageLayout = self.pageLayoutToXmlPageLayout(scoreLayout.pageLayout)
            mxDefaults.append(mxPageLayout)

        if scoreLayout.systemLayout is not None:
            mxSystemLayout = self.systemLayoutToXmlSystemLayout(scoreLayout.systemLayout)
            mxDefaults.append(mxSystemLayout)

        for staffLayout in scoreLayout.staffLayoutList:
            mxStaffLayout = self.staffLayoutToXmlStaffLayout(staffLayout)
            mxDefaults.append(mxStaffLayout)

        # TODO: appearance
        # TODO: music-font
        # TODO: word-font
        # TODO: lyric-font
        # TODO: lyric-language
        return mxDefaults # mostly for testing...
    

    def setPartList(self):
        '''
        Returns a <part-list> and appends it to self.xmlRoot.
        
        This is harder than it looks because MusicXML and music21's idea of where to store
        staff-groups are quite different.
        
        We find each stream in self.partExporterList, then look at the StaffGroup spanners in
        self.spannerBundle.  If the part is the first element in a StaffGroup then we add a
        <staff-group> object with 'start' as the starting point (and same for multiple StaffGroups)
        this is in `staffGroupToXmlPartGroup(sg)`.
        then we add the <score-part> descriptor of the part and its instruments, etc. (currently
        just one!), then we iterate again through all StaffGroups and if this part is the last
        element in a StaffGroup we add a <staff-group> descriptor with type="stop".
        
        This Bach example has four parts and one staff-group bracket linking them:
        
        >>> b = corpus.parse('bwv66.6')
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        
        Needs some strange setup to make this work in a demo.  `.parse()` takes care of all this.
        
        >>> SX.scorePreliminaries()    
        >>> SX.parsePartlikeScore()
        
        >>> mxPartList = SX.setPartList()
        >>> SX.dump(mxPartList)
        <part-list><part-group number="1" type="start">...<score-part 
           id="P1">...<score-part id="P2">...<score-part id="P3">...<score-part 
           id="P4">...<part-group number="1" type="stop" /></part-list>
        '''
        
        spannerBundle = self.spannerBundle
        
        mxPartList = SubElement(self.xmlRoot, 'part-list')
        # mxComponents is just a list 
        # returns a spanner bundle
        staffGroups = spannerBundle.getByClass('StaffGroup')
        #environLocal.printDebug(['got staff groups', staffGroups])
    
        # first, find which parts are start/end of partGroups
        partGroupIndexRef = {} # have id be key
        partGroupIndex = 1 # start by 1 by convention
        for pex in self.partExporterList:
            p = pex.stream
            # check for first
            for sg in staffGroups:
                if sg.isFirst(p):
                    mxPartGroup = self.staffGroupToXmlPartGroup(sg)
                    mxPartGroup.set('number', str(partGroupIndex))
                    # assign the spanner in the dictionary
                    partGroupIndexRef[partGroupIndex] = sg
                    partGroupIndex += 1 # increment for next usage
                    mxPartList.append(mxPartGroup)
            # add score part
            mxScorePart = pex.getXmlScorePart()
            mxPartList.append(mxScorePart)
            # check for last
            activeIndex = None
            for sg in staffGroups:
                if sg.isLast(p):
                    # find the spanner in the dictionary already-assigned
                    for key, value in partGroupIndexRef.items():
                        if value is sg:
                            activeIndex = key
                            break
                    mxPartGroup = Element('part-group')
                    mxPartGroup.set('type', 'stop')
                    if activeIndex is not None:
                        mxPartGroup.set('number', str(activeIndex))
                    mxPartList.append(mxPartGroup)

        return mxPartList
            
    
    def staffGroupToXmlPartGroup(self, staffGroup):
        '''
        Create and configure an mxPartGroup object for the 'start' tag
        from a staff group spanner. Note that this object 
        is not completely formed by this procedure. (number isn't done...)
        
        >>> b = corpus.parse('bwv66.6')
        >>> SX = musicxml.m21ToXml.ScoreExporter(b)
        >>> firstStaffGroup = b.spannerBundle.getByClass('StaffGroup')[0]
        >>> mxPartGroup = SX.staffGroupToXmlPartGroup(firstStaffGroup)
        >>> SX.dump(mxPartGroup)
        <part-group type="start"><group-symbol>bracket</group-symbol><group-barline>yes</group-barline></part-group>

        At this point, you should set the number of the mxPartGroup, since it is required:
        
        >>> mxPartGroup.set('number', str(1))        


        What can we do with it?

        >>> firstStaffGroup.name = 'Voices'
        >>> firstStaffGroup.abbreviation = 'Ch.'
        >>> firstStaffGroup.symbol = 'brace' # 'none', 'brace', 'line', 'bracket', 'square'
        >>> firstStaffGroup.barTogether = False  # True, False, or 'Mensurstrich'
        >>> mxPartGroup = SX.staffGroupToXmlPartGroup(firstStaffGroup)
        >>> SX.dump(mxPartGroup)
        <part-group type="start"><group-name>Voices</group-name><group-abbreviation>Ch.</group-abbreviation><group-symbol>brace</group-symbol><group-barline>no</group-barline></part-group>
        '''
        mxPartGroup = Element('part-group')
        mxPartGroup.set('type', 'start')
        seta = _setTagTextFromAttribute
        seta(staffGroup, mxPartGroup, 'group-name', 'name')
        seta(staffGroup, mxPartGroup, 'group-abbreviation', 'abbreviation')
        seta(staffGroup, mxPartGroup, 'group-symbol', 'symbol')
        
        mxGroupBarline = SubElement(mxPartGroup, 'group-barline')
        if staffGroup.barTogether is True:
            mxGroupBarline.text = 'yes'
        elif staffGroup.barTogether is False:
            mxGroupBarline.text = 'no'
        elif staffGroup.barTogether == 'Mensurstrich':
            mxGroupBarline.text = 'Mensurstrich'
        # TODO: group-time
        # TODO: editorial
        
        #environLocal.printDebug(['configureMxPartGroupFromStaffGroup: mxPartGroup', mxPartGroup])
        return mxPartGroup


    def setIdentification(self):
        if self.mxIdentification is not None:
            mxId = self.mxIdentification
        else:
            mxId = SubElement(self.xmlRoot, 'identification')
            self.mxIdentification = mxId
        
        # creators
        foundOne = False
        if self.scoreMetadata is not None:
            for c in self.scoreMetadata._contributors:
                mxCreator = self.contributorToXmlCreator(c)
                mxId.append(mxCreator)
                foundOne = True
        if foundOne is False:
            mxCreator = SubElement(mxId, 'creator')
            mxCreator.set('type', 'composer')
            mxCreator.text = defaults.author
        
        # TODO: rights.
        self.setEncoding()
        # TODO: source
        # TODO: relation
        # TODO: miscellaneous
        
        
    def setEncoding(self):
        mxEncoding = SubElement(self.mxIdentification, 'encoding')

        # TODO: uncomment this when all is perfect...like old toMxObjects

        mxEncodingDate = SubElement(mxEncoding, 'encoding-date')
        mxEncodingDate.text = str(datetime.date.today()) # right format...
        # TODO: encoder
        mxSoftware = SubElement(mxEncoding, 'software')
        mxSoftware.text = defaults.software

        # TODO: encoding-description
        mxSupportsList = self.setSupports()
        for mxSupports in mxSupportsList:
            mxEncoding.append(mxSupports)
        
    def setSupports(self):
        '''
        return a list of <supports> tags  for what this supports.
        
        Currently just 
        '''
        def getSupport(attribute, type, value, element): # @ReservedAssignment
            su = Element('supports')
            su.set('attribute', attribute)
            su.set('type', type)
            su.set('value', value)
            su.set('element', element)
            return su

        supportsList = []
        s = self.stream
        if s.definesExplicitSystemBreaks is True:
            supportsList.append(getSupport('new-system', 'yes', 'yes', 'print'))

        if s.definesExplicitPageBreaks is True:
            supportsList.append(getSupport('new-page', 'yes', 'yes', 'print'))
        
        return supportsList

    def setTitles(self):
        '''
        puts work, movement-number, movement-title into the self.xmlRoot
        '''
        mdObj = self.scoreMetadata
        if self.scoreMetadata is None:
            mdObj = metadata.Metadata()
        mxScoreHeader = self.xmlRoot
        mxWork = Element('work')
        # TODO: work-number
        if mdObj.title not in (None, ''):
            #environLocal.printDebug(['metadataToMx, got title', mdObj.title])
            mxWorkTitle = SubElement(mxWork, 'work-title')
            mxWorkTitle.text = str(mdObj.title)

        if len(mxWork) > 0:            
            mxScoreHeader.append(mxWork)
            
        if mdObj.movementNumber not in (None, ''):
            mxMovementNumber = SubElement(mxScoreHeader, 'movement-number')
            mxMovementNumber.text = str(mdObj.movementNumber)
        
        # musicxml often defaults to show only movement title       
        # if no movement title is found, get the .title attr
        mxMovementTitle = SubElement(mxScoreHeader, 'movement-title')
        if mdObj.movementName not in (None, ''):
            mxMovementTitle.text = str(mdObj.movementName)
        else: # it is none
            if mdObj.title != None:
                mxMovementTitle.text = str(mdObj.title)
            else:
                mxMovementTitle.text = defaults.title
        
    def contributorToXmlCreator(self, c):
        '''
        Return a <creator> tag from a :class:`~music21.metadata.Contributor` object.
    
        >>> md = metadata.Metadata()
        >>> md.composer = 'frank'
        >>> contrib = md._contributors[0]
        >>> contrib
        <music21.metadata.primitives.Contributor object at 0x...>
        
        >>> SX = musicxml.m21ToXml.ScoreExporter()
        >>> mxCreator = SX.contributorToXmlCreator(contrib)
        >>> SX.dump(mxCreator) 
        <creator type="composer">frank</creator>
        '''
        mxCreator = Element('creator')
        if c.role is not None:
            mxCreator.set('type', str(c.role))
        if c.name is not None:
            mxCreator.text = c.name
        return mxCreator
    
#-------------------------------------------------------------------------------
    
    
class PartExporter(XMLExporterBase):
    
    def __init__(self, partObj=None, parent=None):
        super(PartExporter, self).__init__()
        self.stream = partObj
        self.parent = parent # ScoreParser
        self.xmlRoot = Element('part')
        
        if parent is None:
            self.meterStream = stream.Stream()
            self.refStreamOrTimeRange = [0, 0]
            self.midiChannelList = []
        else:
            self.meterStream = parent.meterStream
            self.refStreamOrTimeRange = parent.refStreamOrTimeRange
            self.midiChannelList = parent.midiChannelList # shared list

        self.instrumentStream = None
        self.firstInstrumentObject = None

        if partObj is not None:
            self.spannerBundle = partObj.spannerBundle
        else:
            self.spannerBundle = spanner.SpannerBundle()

    def parse(self):
        self.instrumentSetup()
        if self.firstInstrumentObject.partId is None:
            self.firstInstrumentObject.partIdRandomize()
        if self.firstInstrumentObject.instrumentId is None:
            self.firstInstrumentObject.instrumentIdRandomize()
            
        self.xmlRoot.set('id', str(self.firstInstrumentObject.partId))
        measureStream = self.stream.getElementsByClass('Measure')
        if len(measureStream) == 0:
            self.fixupNotationFlat() 
        else:
            self.fixupNotationMeasured(measureStream)
        # make sure that all instances of the same class have unique ids
        self.spannerBundle.setIdLocals()
        for m in measureStream:
            measureExporter = MeasureExporter(m, parent=self)
            mxMeasure = measureExporter.parse()
            self.xmlRoot.append(mxMeasure)
            
        return self.xmlRoot        

    def instrumentSetup(self):
        # only things that can be treated as parts are in finalStream
        # get a default instrument if not assigned
        self.instrumentStream = self.stream.getInstruments(returnDefault=True)
        self.firstInstrumentObject = self.instrumentStream[0] # store first, as handled differently
        instIdList = [x.partId for x in self.parent.instrumentList]

        if self.firstInstrumentObject.partId in instIdList: # must have unique ids 
            self.firstInstrumentObject.partIdRandomize() # set new random id

        if (self.firstInstrumentObject.midiChannel == None or
            self.firstInstrumentObject.midiChannel in self.midiChannelList):
            try:
                self.firstInstrumentObject.autoAssignMidiChannel(usedChannels=self.midiChannelList)
            except exceptions21.InstrumentException as e:
                environLocal.warn(str(e))

        # this is shared among all 
        self.midiChannelList.append(self.firstInstrumentObject.midiChannel)
        #environLocal.printDebug(['midiChannel list', self.midiChannelList])

        # add to list for checking on next part
        self.parent.instrumentList.append(self.firstInstrumentObject)
        # force this instrument into this part
        # meterStream is only used here if there are no measures
        # defined in this part

        
    def fixupNotationFlat(self):
        part = self.stream
        part.makeMutable() # must mutate
        # try to add measures if none defined
        # returns a new stream w/ new Measures but the same objects
        part.makeNotation(meterStream=self.meterStream,
                        refStreamOrTimeRange=self.refStreamOrTimeRange,
                        inPlace=True)    
        #environLocal.printDebug(['Stream.streamPartToMx: post makeNotation, length', len(measureStream)])

        # after calling measuresStream, need to update Spanners, as a deepcopy
        # has been made
        # might need to getAll b/c might need spanners 
        # from a higher level container
        #spannerBundle = spanner.SpannerBundle(
        #                measureStream.flat.getAllContextsByClass('Spanner'))
        # only getting spanners at this level
        #spannerBundle = spanner.SpannerBundle(measureStream.flat)
        self.spannerBundle = part.spannerBundle
        
    def fixupNotationMeasured(self, measureStream):
        part = self.stream
        # check that first measure has any attributes in outer Stream
        # this is for non-standard Stream formations (some kern imports)
        # that place key/clef information in the containing stream
        if measureStream[0].clef is None:
            measureStream[0].makeMutable() # must mutate
            outerClefs = part.getElementsByClass('Clef')
            if len(outerClefs) > 0:
                measureStream[0].clef = outerClefs[0]
        if measureStream[0].keySignature is None:
            measureStream[0].makeMutable() # must mutate
            outerKeySignatures = part.getElementsByClass('KeySignature')
            if len(outerKeySignatures) > 0:
                measureStream[0].keySignature = outerKeySignatures[0]
        if measureStream[0].timeSignature is None:
            measureStream[0].makeMutable() # must mutate
            outerTimeSignatures = part.getElementsByClass('TimeSignature')
            if len(outerTimeSignatures) > 0:
                measureStream[0].timeSignature = outerTimeSignatures[0]
        # see if accidentals/beams can be processed
        if not measureStream.streamStatus.haveAccidentalsBeenMade():
            measureStream.makeAccidentals(inPlace=True)
        if not measureStream.streamStatus.haveBeamsBeenMade():
            # if making beams, have to make a deep copy, as modifying notes
            try:
                measureStream.makeBeams(inPlace=True)
            except exceptions21.StreamException: 
                pass
        # TODO: make tuplet brackets once haveTupletBracketsBeenMade is done...
            
        if len(self.spannerBundle) == 0:
            self.spannerBundle = spanner.SpannerBundle(measureStream.flat)
    
        
    def getXmlScorePart(self):    
        '''
        make a <score-part> from a music21 Part object and a parsed mxPart (<part>) element.
        
        contains details about instruments, etc.
        
        called directly by the ScoreExporter
        '''
        mxScorePart = Element('score-part')
        # TODO: identification -- specific metadata... could go here...
        mxScorePart.set('id', self.xmlRoot.get('id'))

        i = self.firstInstrumentObject
        
        mxPartName = SubElement(mxScorePart, 'part-name')
        if i.partName is not None:
            mxPartName.text = i.partName
        else:
            mxPartName.text = defaults.partName
        # TODO: part-name-display
            
        if i.partAbbreviation is not None:
            mxPartAbbreviation = SubElement(mxScorePart, 'part-abbreviation')
            mxPartAbbreviation.text = i.partAbbreviation

        # TODO: part-abbreviation-display
        # TODO: group    
        
        # TODO: unbounded...
        if i.instrumentName is not None or i.instrumentAbbreviation is not None:
            mxScorePart.append(self.instrumentToXmlScoreInstrument(i))

        # TODO: midi-device
        if i.midiProgram is not None:
            mxScorePart.append(self.instrumentToXmlMidiInstrument(i))
            
            
        return mxScorePart
    
    def instrumentToXmlScoreInstrument(self, i):
        mxScoreInstrument = Element('score-instrument')
        mxScoreInstrument.set('id', str(i.instrumentId))
        mxInstrumentName = SubElement(mxScoreInstrument, 'instrument-name')
        mxInstrumentName.text = str(i.instrumentName)
        if i.instrumentAbbreviation is not None:
            mxInstrumentAbbreviation = SubElement(mxScoreInstrument, 'instrument-abbreviation')
            mxInstrumentAbbreviation.text = str(i.instrumentAbbreviation)
        # TODO: instrument-sound
        # TODO: solo / ensemble
        # TODO: virtual-instrument
        
        return mxScoreInstrument

    def instrumentToXmlMidiInstrument(self, i):
        mxMidiInstrument = Element('midi-instrument')
        mxMidiInstrument.set('id', str(i.instrumentId))
        if i.midiChannel == None:
            i.autoAssignMidiChannel()
            # TODO: allocate channels from a higher level
        mxMidiChannel = SubElement(mxMidiInstrument, 'midi-channel')
        mxMidiChannel.text = str(i.midiChannel + 1)
        # TODO: midi-name
        # TODO: midi-bank
        mxMidiProgram = SubElement(mxMidiInstrument, 'midi-program')
        mxMidiProgram.text = str(i.midiProgram + 1)
        # TODO: midi-unpitched
        # TODO: volume
        # TODO: pan
        # TODO: elevation
        return mxMidiInstrument
        

#-------------------------------------------------------------------------------

class MeasureExporter(XMLExporterBase):
    classesToMethods = OrderedDict(
               [('Note', 'noteToXml'),
                ('ChordSymbol', 'chordSymbolToXml'),
                ('Chord', 'chordToXml'),
                ('Rest', 'noteToXml'),
                # Skipping unpitched for now
                ('Dynamic', 'dynamicToXml'),
                ('Segno', 'segnoToXml'),
                ('Coda', 'codaToXml'),
                ('MetronomeMark', 'tempoIndicationToXml'),
                ('MetricModulation', 'tempoIndicationToXml'),
                ('TextExpression', 'textExpressionToXml'),
                ('RepeatEpxression', 'textExpressionToXml'),
                ('Clef', 'midmeasureClefToXml'),
               ])
    ignoreOnParseClasses = set(['KeySignature', 'LayoutBase', 'TimeSignature', 'Barline'])
    
    
    def __init__(self, measureObj=None, parent=None):
        super(MeasureExporter, self).__init__()
        if measureObj is not None:
            self.stream = measureObj
        else: # no point, but...
            self.stream = stream.Measure()
        
        self.parent = parent # PartExporter
        self.xmlRoot = Element('measure')
        self.currentDivisions = defaults.divisionsPerQuarter

        # TODO: allow for mid-measure transposition changes.
        self.transpositionInterval = None
        self.mxTranspose = None
        self.measureOffsetStart = 0.0
        self.offsetInMeasure = 0.0
        self.currentVoiceId = None
        
        self.rbSpanners = [] # rightBarline repeat spanners
        
        if parent is None:
            self.spannerBundle = spanner.SpannerBundle()
        else:
            self.spannerBundle = parent.spannerBundle

        self.objectSpannerBundle = self.spannerBundle # will change for each element.

    def parse(self):
        self.setTranspose()
        self.setRbSpanners()
        self.setMxAttributes()
        self.setMxPrint()
        self.setMxAttributesObject()
        self.setLeftBarline()
        self.mainElementsParse()
        self.setRightBarline()
        return self.xmlRoot
        
    def mainElementsParse(self):
        m = self.stream
        # need to handle objects in order when creating musicxml 
        # we thus assume that objects are sorted here

        if m.hasVoices():
            # TODO... Voice not Stream
            nonVoiceMeasureItems = m.getElementsNotOfClass('Stream')
        else:
            nonVoiceMeasureItems = m # use self.

        for v in m.voices:
            # Assumes voices are flat...
            self.parseFlatElements(v)
        
        self.parseFlatElements(nonVoiceMeasureItems)
    
    def parseFlatElements(self, m):
        '''
        m here can be a Measure or Voice, but
        flat...
        
        '''
        # TODO: fix mid-measure clef change with voices and part-staff in Schoenberg op. 19 no 2
        # staff 2, m. 6...
        root = self.xmlRoot
        divisions = self.currentDivisions
        self.offsetInMeasure = 0.0
        if 'Voice' in m.classes:
            voiceId = m.id
        else:
            voiceId = None
        
        self.currentVoiceId = voiceId
        for obj in m:
            self.parseOneElement(obj, m)
        
        if voiceId is not None:
            mxBackup = Element('backup')
            mxDuration = SubElement(mxBackup, 'duration')
            mxDuration.text = str(int(round(divisions * self.offsetInMeasure)))
            # TODO: editorial
            root.append(mxBackup)
        self.currentVoiceId = None

    def parseOneElement(self, obj, m):
        '''
        parse one element completely and add it to xmlRoot, updating
        offsetInMeasure, etc.
        
        m is either a measure or a voice object.
        '''
        root = self.xmlRoot
        self.objectSpannerBundle = self.spannerBundle.getBySpannedElement(obj)
        preList, postList = self.prePostObjectSpanners(obj)
        
        for sp in preList: # directions that precede the element
            root.append(sp)
            
        classes = obj.classes
        if 'GeneralNote' in classes:
            self.offsetInMeasure += obj.duration.quarterLength

        # split at durations...
        if 'GeneralNote' in classes and obj.duration.type == 'complex':
            objList = obj.splitAtDurations()
        else:
            objList = [obj]
        
        
        ignore = False
        for className, methName in self.classesToMethods.items():
            if className in classes:
                meth = getattr(self, methName)
                for o in objList:
                    meth(o)
                ignore = True
                break
        if ignore is False:
            for className in classes:
                if className in self.ignoreOnParseClasses:
                    ignore = True
                    break
            if ignore is False:
                environLocal.printDebug(['did not convert object', obj])

        for sp in postList: # directions that follow the element
            root.append(sp)

    def prePostObjectSpanners(self, target):
        '''
        return two lists or empty tuples: 
        (1) spanners related to the object that should appear before the object
        to the <measure> tag. (2) spanners related to the object that should appear after the
        object in the measure tag.
        '''
        def getProc(su, target):
            if len(su) == 1: # have a one element wedge
                proc = ('first', 'last')
            else:
                if su.isFirst(target):
                    proc = ('first',)
                elif su.isLast(target):
                    proc = ('last',)
                else:
                    proc = ()
            return proc
        
        spannerBundle = self.objectSpannerBundle
        if len(spannerBundle) == 0:
            return (), ()

        preList = []
        postList = []
        
        # number, type is assumed; 
        # tuple: first is the elementType, 
        #        second: tuple of parameters to set,
        paramsSet = {'Ottava': ('octave-shift', ('size',)),
                     # TODO: attrGroup: dashed-formatting, print-style
                     'DynamicWedge': ('wedge', ('spread',)),
                     # TODO: niente, attrGroups: line-type, dashed-formatting, position, color
                     'Line': ('bracket', ('line-end', 'end-length'))
                     # TODO: dashes???
                     }

        for m21spannerClass, infoTuple in paramsSet.items():
            mxtag, parameterSet = infoTuple
            for su in spannerBundle.getByClass(m21spannerClass):
                for posSub in getProc(su, target):
                    # create new tag
                    mxElement = Element(mxtag)
                    mxElement.set('number', str(su.idLocal))
                    if m21spannerClass == 'Line':
                        mxElement.set('line-type', str(su.lineType))
                    
                    if posSub == 'first':
                        pmtrs = su.getStartParameters()
                    elif posSub == 'last':
                        pmtrs = su.getEndParameters()
                    else:
                        pmtrs = None
                        
                    if pmtrs is not None:
                        mxElement.set('type', str(pmtrs['type']))
                        for attrName in parameterSet:
                            if pmtrs[attrName] is not None:
                                mxElement.set(attrName, str(pmtrs[attrName]))
                    mxDirection = Element('direction')
                    if su.placement is not None:
                        mxDirection.set('placement', str(su.placement))
                    mxDirectionType = SubElement(mxDirection, 'direction-type')
                    mxDirectionType.append(mxElement)
                    
                    if posSub == 'first':
                        preList.append(mxDirection)
                    else:
                        postList.append(mxDirection)
        
        return preList, postList
    
    def objectAttachedSpannersToNotations(self, obj):
        '''
        return a list of <notations> from spanners related to the object that should appear 
        in the notations tag (slurs, slides, etc.)
        '''
        notations = []
        sb = self.objectSpannerBundle
        if len(sb) == 0:
            return notations

        ornaments = []
        
        for su in sb.getByClass('Slur'):
            mxSlur = Element('slur')
            if su.isFirst(obj):
                mxSlur.set('type', 'start')
            elif su.isLast(obj):
                mxSlur.set('type', 'stop')
            else:
                continue # do not put a notation on mid-slur notes.
            mxSlur.set('number', str(su.idLocal))
            if su.placement is not None:
                mxSlur.set('placement', str(su.placement))
            notations.append(mxSlur)

        for su in sb.getByClass('Glissando'):
            mxGlissando = Element('glissando')
            mxGlissando.set('number', str(su.idLocal))
            if su.lineType is not None:
                mxGlissando.set('line-type', str(su.lineType))
            # is this note first in this spanner?
            if su.isFirst(obj):
                if su.label is not None:
                    mxGlissando.text = str(su.label)
                mxGlissando.set('type', 'start')
            elif su.isLast(obj):
                mxGlissando.set('type', 'stop')
            else:
                continue # do not put a notation on mid-gliss notes.
            # placement???
            notations.append(mxGlissando)

        # These add to Ornaments...
        
        for su in sb.getByClass('TremoloSpanner'):
            mxTrem = Element('tremolo')
            mxTrem.text = str(su.numberOfMarks)
            if su.isFirst(obj):
                mxTrem.set('type', 'start')
            elif su.isLast(obj):
                mxTrem.set('type', 'stop')
            else:
                # this is always an error for tremolos
                environLocal.printDebug(['spanner w/ a component that is neither a start nor an end.', su, obj])
            if su.placement is not None:
                mxTrem.set('placement', str(su.placement))
            # Tremolos get in a separate ornaments tag...
            ornaments.append(mxTrem)

        for su in sb.getByClass('TrillExtension'):
            mxWavyLine = Element('wavy-line')
            mxWavyLine.set('number', str(su.idLocal))
            # is this note first in this spanner?
            if su.isFirst(obj):
                mxWavyLine.set('type', 'start')
            elif su.isLast(obj):
                mxWavyLine.set('type', 'stop')
            else:
                continue # do not put a wavy-line tag on mid-trill notes
            if su.placement is not None:
                mxWavyLine.set('placement', su.placement)
            ornaments.append(mxWavyLine)



        if len(ornaments) > 0:
            mxOrn = Element('ornaments')
            for orn in ornaments:
                mxOrn.append(orn)
            notations.append(mxOrn)

        return notations

    def noteToXml(self, n, addChordTag=False):
        '''
        Translate a music21 :class:`~music21.note.Note` or a Rest into a
        list of :class:`~music21.musicxml.mxObjects.Note` objects.
    
        Because of "complex" durations, the number of 
        `musicxml.mxObjects.Note` objects could be more than one.
    
        Note that, some note-attached spanners, such 
        as octave shifts, produce direction (and direction types) 
        in this method.
        
        >>> n = note.Note('D#5')
        >>> n.quarterLength = 3
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> len(MEX.xmlRoot)
        0
        >>> mxNote = MEX.noteToXml(n)
        >>> MEX.dump(mxNote)
        <note><pitch><step>D</step><alter>1</alter><octave>5</octave></pitch><duration>30240</duration><type>half</type><dot /><accidental>sharp</accidental></note>
        >>> len(MEX.xmlRoot)
        1
        

        >>> r = note.Rest()
        >>> r.quarterLength = 1.0/3
        >>> r.duration.tuplets[0].type = 'start'
        >>> mxRest = MEX.noteToXml(r)
        >>> MEX.dump(mxRest)
        <note><rest /><duration>3360</duration><type>eighth</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes><normal-type>eighth</normal-type></time-modification><notations><tuplet bracket="yes" placement="above" type="start" /></notations></note>
        >>> len(MEX.xmlRoot)
        2
        
        >>> n.notehead = 'diamond'
        >>> mxNote = MEX.noteToXml(n)
        >>> MEX.dump(mxNote)
        <note><pitch><step>D</step><alter>1</alter><octave>5</octave></pitch><duration>30240</duration><type>half</type><dot /><accidental>sharp</accidental><notehead parentheses="no">diamond</notehead></note>
         
        TODO: Test with spanners...
        '''
        # TODO: attrGroup x-position
        # TODO: attrGroup font
        # TODO: attr: dynamics
        # TODO: attr: end-dynamics
        # TODO: attr: attack
        # TODO: attr: release
        # TODO: attr: time-only
        mxNote = Element('note')
        if n.duration.isGrace is True:
            SubElement(mxNote, 'grace')

        # TODO: cue...
        if n.color is not None:
            mxNote.set('color', normalizeColor(n.color))
        if n.hideObjectOnPrint is True:
            mxNote.set('print-object', 'no')
            mxNote.set('print-spacing', 'yes')
            
        for art in n.articulations:
            if 'Pizzicato' in art.classes:
                mxNote.set('pizzicato', 'yes')
        
        if addChordTag:
            SubElement(mxNote, 'chord')
        
        if hasattr(n, 'pitch'):
            mxPitch = self.pitchToXml(n.pitch)
            mxNote.append(mxPitch)
        else: 
            # assume rest until unpitched works
            # TODO: unpitched
            SubElement(mxNote, 'rest')

        if n.duration.isGrace is not True:
            mxDuration = self.durationXml(n.duration)
            mxNote.append(mxDuration)
            # divisions only
        # TODO: skip if cue:
        if n.tie is not None:
            mxTieList = self.tieToXmlTie(n.tie)
            for t in mxTieList:
                mxNote.append(t)
        
            
        # TODO: instrument
        # TODO: footnote
        # TODO: level
        if self.currentVoiceId is not None:
            mxVoice = SubElement(mxNote, 'voice')
            try:
                mxVoice.text = str(self.currentVoiceId + 1)
            except TypeError:
                mxVoice.text = str(self.currentVoiceId)
        
        if n.duration.type != 'zero':
            mxType = Element('type')
            mxType.text = typeToMusicXMLType(n.duration.type)
            mxNote.append(mxType)
        
        for _ in range(n.duration.dots):
            SubElement(mxNote, 'dot')
            # TODO: dot placement...
        if (hasattr(n, 'pitch') and 
                n.pitch.accidental is not None and 
                n.pitch.accidental.displayStatus in (True, None)):
            mxAccidental = accidentalToMx(n.pitch.accidental)
            mxNote.append(mxAccidental)
        if len(n.duration.tuplets) > 0:
            for tup in n.duration.tuplets:
                mxTimeModification = self.tupletToTimeModification(tup)
                mxNote.append(mxTimeModification)
        # TODO: stem
        if (hasattr(n, 'notehead') and 
                (n.notehead != 'normal' or  # TODO: restore... needed for complete compatibility with toMxObjects...
                 n.noteheadFill is not None or
                 n.color not in (None, ''))
            ):
            mxNotehead = self.noteheadToXml(n)
            mxNote.append(mxNotehead)
        # TODO: notehead-text
        if hasattr(n, 'stemDirection') and n.stemDirection != 'unspecified':
            mxStem = SubElement(mxNote, 'stem')
            sdtext = n.stemDirection
            if sdtext == 'noStem':
                sdtext = 'none'
            mxStem.text = sdtext
        
        # TODO: staff
        if hasattr(n, 'beams') and n.beams:
            nBeamsList = self.beamsToXml(n.beams)
            for mxB in nBeamsList:
                mxNote.append(mxB)
    
        mxNotationsList = self.noteToNotations(n)
        if len(mxNotationsList) > 0: # TODO: make to zero -- this is just for perfect old compat.
            mxNotations = SubElement(mxNote, 'notations')
            for mxN in mxNotationsList:
                mxNotations.append(mxN)

        for lyricObj in n.lyrics:
            mxNote.append(self.lyricToXml(lyricObj))
        # TODO: play
        self.xmlRoot.append(mxNote)
        return mxNote

    def chordToXml(self, c):
        '''
        Returns a list of <note> tags, all but the first with a <chord/> tag on them.
        And appends them to self.xmlRoot
        
        Attributes of notes are merged from different locations: first from the
        duration objects, then from the pitch objects. Finally, GeneralNote
        attributes are added.
            
        >>> ch = chord.Chord()
        >>> ch.quarterLength = 2
        >>> b = pitch.Pitch('A-2')
        >>> c = pitch.Pitch('D3')
        >>> d = pitch.Pitch('E4')
        >>> e = [b,c,d]
        >>> ch.pitches = e
        
        >>> len(ch.pitches)
        3
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> len(MEX.xmlRoot)
        0
        >>> mxNoteList = MEX.chordToXml(ch)
        >>> len(mxNoteList) # get three mxNotes
        3
        >>> len(MEX.xmlRoot)
        3
        
        >>> MEX.dump(mxNoteList[0])
        <note><pitch><step>A</step><alter>-1</alter><octave>2</octave></pitch><duration>10080</duration><type>quarter</type><accidental>flat</accidental></note>
        >>> MEX.dump(mxNoteList[1])
        <note><chord /><pitch><step>D</step><octave>3</octave></pitch><duration>10080</duration><type>quarter</type></note>
        >>> MEX.dump(mxNoteList[2])
        <note><chord /><pitch><step>E</step><octave>4</octave></pitch><duration>10080</duration><type>quarter</type></note>
            
    
        Test that notehead translation works:
        
        >>> g = pitch.Pitch('g3')
        >>> h = note.Note('b4')
        >>> h.notehead = 'diamond'
        >>> ch2 = chord.Chord([g, h])
        >>> ch2.quarterLength = 2.0
        >>> mxNoteList = MEX.chordToXml(ch2)
        >>> MEX.dump(mxNoteList[1])
        <note><chord /><pitch><step>B</step><octave>4</octave></pitch><duration>20160</duration><type>half</type><notehead parentheses="no">diamond</notehead></note>
        '''
        mxNoteList = []
        for i, n in enumerate(c):
            addChordTag = True if i > 0 else False
            mxNoteList.append(self.noteToXml(n, addChordTag=addChordTag)) 
        return mxNoteList

            
    def durationXml(self, dur):
        '''
        Convert a duration.Duration object to a <duration> tag using self.currentDivisions
        
        >>> d = duration.Duration(1.5)
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> MEX.currentDivisions = 10
        >>> mxDuration = MEX.durationXml(d)
        >>> MEX.dump(mxDuration)
        <duration>15</duration>
        '''
        mxDuration = Element('duration')
        mxDuration.text = str(int(round(self.currentDivisions * dur.quarterLength)))
        return mxDuration
    
    def pitchToXml(self, p):
        '''
        convert a pitch to xml... does not create the <accidental> tag...
        
        >>> p = pitch.Pitch('D#5')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxPitch = MEX.pitchToXml(p)
        >>> MEX.dump(mxPitch)
        <pitch><step>D</step><alter>1</alter><octave>5</octave></pitch>
        '''
        mxPitch = Element('pitch')
        _setTagTextFromAttribute(p, mxPitch, 'step')
        if p.accidental is not None:
            mxAlter = SubElement(mxPitch, 'alter')
            mxAlter.text = str(common.numToIntOrFloat(p.accidental.alter))
        _setTagTextFromAttribute(p, mxPitch, 'octave', 'implicitOctave')
        return mxPitch
    
    def tupletToTimeModification(self, tup):
        '''
        >>> t = duration.Tuplet(11, 8)
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxTimeMod = MEX.tupletToTimeModification(t)
        >>> MEX.dump(mxTimeMod)
        <time-modification><actual-notes>11</actual-notes><normal-notes>8</normal-notes><normal-type>eighth</normal-type></time-modification>
        '''
        mxTimeModification = Element('time-modification')
        _setTagTextFromAttribute(tup, mxTimeModification, 'actual-notes', 'numberNotesActual')
        _setTagTextFromAttribute(tup, mxTimeModification, 'normal-notes', 'numberNotesNormal')
        mxNormalType = SubElement(mxTimeModification, 'normal-type')
        mxNormalType.text = typeToMusicXMLType(tup.durationNormal.type)
        if tup.durationNormal.dots > 0:
            for i in range(tup.durationNormal.dots):
                SubElement(mxTimeModification, 'normal-dot')
                
        return mxTimeModification
    
    def noteheadToXml(self, n):
        '''
        Translate a music21 :class:`~music21.note.Note` object 
        into a <notehead> tag
        
        
        >>> n = note.Note('C#4')
        >>> n.notehead = 'diamond'
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxN = MEX.noteheadToXml(n)
        >>> MEX.dump(mxN)
        <notehead parentheses="no">diamond</notehead>
    
        >>> n1 = note.Note('c3')
        >>> n1.color = 'red'
        >>> n1.notehead = 'diamond'
        >>> n1.noteheadParenthesis = True
        >>> n1.noteheadFill = False
        >>> mxN = MEX.noteheadToXml(n1)
        >>> MEX.dump(mxN)
        <notehead color="#FF0000" filled="no" parentheses="yes">diamond</notehead>
        '''        
        mxNotehead = Element('notehead')
        nh = n.notehead
        if nh is None:
            nh = 'none'
        mxNotehead.text = nh 
        setb = _setAttributeFromAttribute
        setb(n, mxNotehead, 'filled', 'noteheadFill', transform=xmlObjects.booleanToYesNo)
        setb(n, mxNotehead, 'parentheses', 'noteheadParenthesis', transform=xmlObjects.booleanToYesNo)
        # TODO: font
        if n.color not in (None, ''):
            color = normalizeColor(n.color)
            mxNotehead.set('color', color)
        return mxNotehead
    
    def noteToNotations(self, n):
        '''
        Take information from .expressions,
        .articulations, and spanners to
        make the <notations> tag for a note.
        '''
        mxArticulations = None
        mxTechnicalMark = None
        mxOrnaments = None

        notations = []

        for expObj in n.expressions:
            mxExpression = self.expressionToXml(expObj)
            if mxExpression is None:
                #print("Could not convert expression: ", mxExpression)
                # TODO: should not!
                continue
            if 'Ornament' in expObj.classes:
                if mxOrnaments is None:
                    mxOrnaments = Element('ornaments')
                mxOrnaments.append(mxExpression)
                #print(mxExpression)
            else:
                notations.append(mxExpression)

        for artObj in n.articulations:
            if 'TechnicalIndication' in artObj.classes:
                if mxTechnicalMark is None:
                    mxTechnicalMark = Element('technical')
                mxTechnicalMark.append(self.articulationToXmlTechnical(artObj))
            else:
                if mxArticulations is None:
                    mxArticulations = Element('articulations')
                mxArticulations.append(self.articulationToXmlArticulation(artObj))
        
        # TODO: attrGroup: print-object (for individual notations)
        # TODO: editorial (hard! -- requires parsing again in order...)
        
        # <tied>
        if n.tie is not None:
            tiedList = self.tieToXmlTied(n.tie)
            notations.extend(tiedList)
        # <tuplet>
        for tup in n.duration.tuplets:
            tupTagList = self.tupletToXmlTuplet(tup)
            notations.extend(tupTagList)

        notations.extend(self.objectAttachedSpannersToNotations(n))
        # TODO: slur            
        # TDOO: glissando
        # TODO: slide
                
        for x in (mxArticulations, 
                  mxTechnicalMark, 
                  mxOrnaments):
            if x is not None and len(x) > 0:
                notations.append(x)    

        # TODO: dynamics in notations
        # TODO: arpeggiate
        # TODO: non-arpeggiate
        # TODO: accidental-mark
        # TODO: other-notation
        return notations

    def tieToXmlTie(self, t):
        '''
        returns a list of ties from a Tie object.
        
        A 'continue' tie requires two <tie> tags to represent.
        
        >>> t = tie.Tie('continue')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> tieList = MEX.tieToXmlTie(t)
        >>> for mxT in tieList: 
        ...     MEX.dump(mxT)
        <tie type="stop" />
        <tie type="start" />        
        '''
        mxTieList = []
        
        if t.type == 'continue':
            musicxmlTieType = 'stop'
        else:
            musicxmlTieType = t.type
        mxTie = Element('tie')
        mxTie.set('type', musicxmlTieType)
        mxTieList.append(mxTie)
        
        if t.type == 'continue':
            mxTie = Element('tie')
            mxTie.set('type', 'start')
            mxTieList.append(mxTie)
            
        return mxTieList
        
    

    def tieToXmlTied(self, t):
        '''
        In musicxml, a tie is represented in sound
        by the tie tag (near the pitch object), and
        the <tied> tag in notations.  This
        creates the <tied> tag.
        
        Returns a list since a music21
        "continue" tie type needs two tags
        in musicxml.  List may be empty
        if tie.style == "hidden"

        >>> t = tie.Tie('continue')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> tiedList = MEX.tieToXmlTied(t)
        >>> for mxT in tiedList: 
        ...     MEX.dump(mxT)
        <tied type="stop" />
        <tied type="start" />
        
        >>> t.style = 'hidden'
        >>> tiedList = MEX.tieToXmlTied(t)
        >>> len(tiedList)
        0
        '''
        if t.style == 'hidden':
            return []

        mxTiedList = []
        if t.type == 'continue':
            musicxmlTieType = 'stop'
        else:
            musicxmlTieType = t.type
        
        mxTied = Element('tied')
        mxTied.set('type', musicxmlTieType)
        mxTiedList.append(mxTied)
        
        if t.type == 'continue':            
            mxTied = Element('tied')
            mxTied.set('type', 'start')
            mxTiedList.append(mxTied)
        
        # TODO: attr: number (distinguishing ties on enharmonics)
        # TODO: attrGroup: line-type
        # TODO: attrGroup: dashed-formatting
        # TODO: attrGroup: position
        # TODO: attrGroup: placement
        # TODO: attrGroup: orientation
        # TODO: attrGroup: bezier
        # TODO: attrGroup: color
        
        return mxTiedList

    def tupletToXmlTuplet(self, tuplet):
        '''
        In musicxml, a tuplet is represented by
        a timeModification and visually by the
        <notations><tuplet> tag.  This method
        creates the latter.

        Returns a list of them because a 
        startStop type tuplet needs two tuplet
        brackets.

        TODO: make sure something happens if
        makeTupletBrackets is not set.

        >>> t = duration.Tuplet(11, 8)
        >>> t.type = 'start'
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxTup = MEX.tupletToXmlTuplet(t)
        >>> len(mxTup)
        1
        >>> MEX.dump(mxTup[0])
        <tuplet bracket="yes" placement="above" type="start" />
        '''
        if tuplet.type in (None, ''):
            return []
        
        if tuplet.type not in ('start', 'stop', 'startStop'):
            raise ToMxObjectsException("Cannot create music XML from a tuplet of type " + tuplet.type)

        if tuplet.type == 'startStop': # need two musicxml
            localType = ['start', 'stop']
        else:
            localType = [tuplet.type] # place in list

        retList = []
        
        # TODO: tuplet-actual different from time-modification
        # TODO: tuplet-normal
        # TODO: attr: show-type
        # TODO: attrGroup: position
        
        for tupletType in localType:
            mxTuplet = Element('tuplet')
            mxTuplet.set('type', tupletType)
            # only provide other parameters if this tuplet is a start
            if tupletType == 'start':
                mxTuplet.set('bracket', 
                             xmlObjects.booleanToYesNo(tuplet.bracket))
                if tuplet.placement is not None:
                    mxTuplet.set('placement', tuplet.placement)
                if tuplet.tupletActualShow == 'none':
                    mxTuplet.set('show-number', 'none')
            retList.append(mxTuplet)
        return retList

    def expressionToXml(self, expression):
        '''
        Convert a music21 Expression (expression or ornament)
        to a musicxml tag; 
        return None if no conversion is possible.
        
        >>> t = expressions.InvertedTurn()
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxExpression = MEX.expressionToXml(t)
        >>> MEX.dump(mxExpression)
        <inverted-turn placement="above" />
        
        Two special types...
        
        >>> f = expressions.Fermata()
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxExpression = MEX.expressionToXml(f)
        >>> MEX.dump(mxExpression)
        <fermata type="inverted" />
        
        >>> t = expressions.Tremolo()
        >>> t.numberOfMarks = 4
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxExpression = MEX.expressionToXml(t)
        >>> MEX.dump(mxExpression)
        <tremolo type="single">4</tremolo>        
        '''
        mapping = OrderedDict([
                   ('Trill', 'trill-mark'),
                   # TODO: delayed-inverted-turn
                   # TODO: vertical-turn
                   # TODO: 'delayed-turn'
                   ('InvertedTurn', 'inverted-turn'),
                   # last as others are subclasses
                   ('Turn', 'turn'), 
                   ('InvertedMordent', 'inverted-mordent'),
                   ('Mordent', 'mordent'),
                   ('Shake', 'shake'),
                   ('Schleifer', 'schleifer'),
                   # TODO: 'accidental-mark'
                   ('Tremolo', 'tremolo'), # non-spanner
                   # non-ornaments...
                   ('Fermata', 'fermata'),
                   # keep last...
                   ('Ornament', 'other-ornament'),
                   ])
        mx = None
        classes = expression.classes
        for k, v in mapping.items():
            if k in classes:
                mx = Element(v)
                break
        if mx is None:
            environLocal.printDebug(['no musicxml conversion for:', expression])
            return 
        
        # TODO: print-style
        # TODO: trill-sound
        if hasattr(expression, 'placement') and expression.placement is not None:
            mx.set('placement', expression.placement)
        if 'Fermata' in classes:
            mx.set('type', str(expression.type))
        
        
        if 'Tremolo' in classes:
            mx.set('type', 'single')
            mx.text = str(expression.numberOfMarks)
        
        return mx
        
        
        
    def articulationToXmlArticulation(self, articulationMark):
        '''
        Returns a class (mxArticulationMark) that represents the
        MusicXML structure of an articulation mark.
    
        >>> a = articulations.Accent()
        >>> a.placement = 'below'
        
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxArticulationMark = MEX.articulationToXmlArticulation(a)
        >>> MEX.dump(mxArticulationMark)
        <accent placement="below" />

        >>> a = articulations.Staccatissimo()
        >>> a.placement = 'below'
        
        >>> mxArticulationMark = MEX.articulationToXmlArticulation(a)
        >>> MEX.dump(mxArticulationMark)
        <staccatissimo placement="below" />

        '''
        # TODO: OrderedDict
        # these articulations have extra information
        # TODO: strong-accent
        # TODO: scoop/plop/doit/falloff - empty-line
        # TODO: breath-mark
        # TODO: other-articulation
        
        musicXMLArticulationName = None
        for c in xmlObjects.ARTICULATION_MARKS_REV:
            if isinstance(articulationMark, c):
                musicXMLArticulationName = xmlObjects.ARTICULATION_MARKS_REV[c]
                break
        if musicXMLArticulationName is None:
            musicXMLArticulationName = 'other-articulation'
            #raise ToMxObjectsException("Cannot translate %s to musicxml" % articulationMark)
        mxArticulationMark = Element(musicXMLArticulationName)
        mxArticulationMark.set('placement', articulationMark.placement)
        #mxArticulations.append(mxArticulationMark)
        return mxArticulationMark
    
    def articulationToXmlTechnical(self, articulationMark):
        '''
        Returns a tag that represents the
        MusicXML structure of an articulation mark that is primarily a TechnicalIndication.
        
        >>> a = articulations.UpBow()
        >>> a.placement = 'below'

        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxTechnicalMark = MEX.articulationToXmlTechnical(a)
        >>> MEX.dump(mxTechnicalMark)
        <up-bow placement="below" />
        '''
        # TODO: OrderedDict to make Technical Indication work...
        # these technical have extra information
        # TODO: handbell
        # TODO: arrow
        # TODO: hole
        # TODO: heel-toe
        # TODO: bend
        # TODO: pull-off/hammer-on
        # TODO: string
        # TODO: fret
        # TODO: fingering
        # TODO: harmonic
        
        musicXMLTechnicalName = None
        for c in xmlObjects.TECHNICAL_MARKS_REV:
            if isinstance(articulationMark, c):
                musicXMLTechnicalName = xmlObjects.TECHNICAL_MARKS_REV[c]
                break
        if musicXMLTechnicalName is None:
            raise ToMxObjectsException("Cannot translate technical indication %s to musicxml" % articulationMark)
        mxTechnicalMark = Element(musicXMLTechnicalName)
        mxTechnicalMark.set('placement', articulationMark.placement)
        #mxArticulations.append(mxArticulationMark)
        return mxTechnicalMark
    
    
    def chordSymbolToXml(self, cs):
        '''
        Convert a ChordSymbol object to an mxHarmony object.
           
        >>> cs = harmony.ChordSymbol()
        >>> cs.root('E-')
        >>> cs.bass('B-')
        >>> cs.inversion(2, transposeOnSet = False)
        >>> cs.chordKind = 'major'
        >>> cs.chordKindStr = 'M'
        >>> cs
        <music21.harmony.ChordSymbol E-/B->

        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> MEX.currentDivisions = 10

        >>> mxHarmony = MEX.chordSymbolToXml(cs)
        >>> MEX.dump(mxHarmony)
        <harmony><root><root-step>E</root-step><root-alter>-1.0</root-alter></root><kind text="M">major</kind><inversion>2</inversion><bass><bass-step>B</bass-step><bass-alter>-1.0</bass-alter></bass></harmony>

        Now give function...
        
        >>> cs.romanNumeral = 'I64'
        >>> mxHarmony = MEX.chordSymbolToXml(cs)
        >>> MEX.dump(mxHarmony)
        <harmony><function>I64</function><kind text="M">major</kind><inversion>2</inversion><bass><bass-step>B</bass-step><bass-alter>-1.0</bass-alter></bass></harmony>
     
        >>> hd = harmony.ChordStepModification()
        >>> hd.modType = 'alter'
        >>> hd.interval = -1
        >>> hd.degree = 3
        >>> cs.addChordStepModification(hd)
     
        >>> mxHarmony = MEX.chordSymbolToXml(cs)
        >>> MEX.dump(mxHarmony)
        <harmony><function>I64</function><kind text="M">major</kind><inversion>2</inversion><bass><bass-step>B</bass-step><bass-alter>-1.0</bass-alter></bass><degree><degree-value>3</degree-value><degree-alter>-1</degree-alter><degree-type>alter</degree-type></degree></harmony>
    
        Test altered chords:
        
        Is this correct?
    
        >>> f = harmony.ChordSymbol('F sus add 9')
        >>> f
        <music21.harmony.ChordSymbol F sus add 9>
        >>> mxHarmony = MEX.chordSymbolToXml(f)
        >>> MEX.dump(mxHarmony)
        <harmony><root><root-step>G</root-step></root><kind>suspended-fourth</kind><inversion>3</inversion><degree><degree-value>9</degree-value><degree-alter /><degree-type>add</degree-type></degree></harmony>
        
        MusicXML uses "dominant" for "dominant-seventh" so check aliases back...
    
        >>> dom7 = harmony.ChordSymbol('C7')
        >>> dom7.chordKind
        'dominant-seventh'
        >>> mxHarmony = MEX.chordSymbolToXml(dom7)
        >>> MEX.dump(mxHarmony)
        <harmony><root><root-step>C</root-step></root><kind>dominant</kind></harmony>
        
        set writeAsChord to not get a symbol, but the notes.  Will return a list of notes.
        
        >>> dom7.writeAsChord = True
        >>> harmonyList = MEX.chordSymbolToXml(dom7)
        >>> len(harmonyList)
        4
        >>> MEX.dump(harmonyList[0])
        <note><pitch><step>C</step><octave>3</octave></pitch><duration>10</duration><type>quarter</type></note>
        '''
        # TODO: frame # fretboard
        # TODO: offset
        # TODO: editorial
        # TODO: staff
        # TODO: attrGroup: print-object
        # TODO: attr: print-frame
        # TODO: attrGroup: print-style
        # TODO: attrGroup: placement
                
        if cs.writeAsChord is True:
            return self.chordToXml(cs)

        from music21 import harmony
        mxHarmony = Element('harmony')

        csRoot = cs.root()
        csBass = cs.bass(find=False)
        # TODO: do not look at ._attributes...
        if cs._roman is not None:
            mxFunction = SubElement(mxHarmony, 'function')
            mxFunction.text = cs.romanNumeral.figure
        elif csRoot is not None:
            mxRoot = SubElement(mxHarmony, 'root')    
            mxStep = SubElement(mxRoot, 'root-step')
            mxStep.text = str(csRoot.step) 
            # not a todo, text attribute; use element.
            # TODO: attrGroup: print-style 
                    
            if csRoot.accidental is not None:
                mxAlter = SubElement(mxRoot, 'root-alter')
                mxAlter.text = str(csRoot.accidental.alter)
                # TODO: attrGroup: print-object (why here)??
                # TODO: attrGroup: print-style
                # TODO: attr: location (left, right)
        else:
            environLocal.printDebug(['need either a root or a _roman to show'])
            return
        
        mxKind = SubElement(mxHarmony, 'kind')
        cKind = cs.chordKind
        for xmlAlias in harmony.CHORD_ALIASES:
            if harmony.CHORD_ALIASES[xmlAlias] == cKind:
                cKind = xmlAlias

        mxKind.text = str(cKind)
        if cs.chordKindStr not in (None, ""):
            mxKind.set('text', cs.chordKindStr)
        # TODO: attr: use-symbols
        # TODO: attr: stack-degrees
        # TODO: attr: parentheses-degrees
        # TODO: attr: bracket-degrees
        # TODO: attrGroup: print-style
        # TODO: attrGroup: halign
        # TODO: attrGroup: valign
        csInv = cs.inversion()
        if csInv not in (None, 0):
            mxInversion = SubElement(mxHarmony, 'inversion')
            mxInversion.text = str(csInv)
        
        if csBass is not None and (csRoot is None or csRoot.name != csBass.name):
            # TODO.. reuse above from Root...
            mxBass = SubElement(mxHarmony, 'bass')
            mxStep = SubElement(mxBass, 'bass-step')
            mxStep.text = str(csBass.step) 
            # not a todo, text attribute; use element.
            # TODO: attrGroup: print-style 
                    
            if csBass.accidental is not None:
                mxAlter = SubElement(mxBass, 'bass-alter')
                mxAlter.text = str(csBass.accidental.alter)
                # TODO: attrGroup: print-object (why here)??
                # TODO: attrGroup: print-style
                # TODO: attr: location (left, right)       

        if len(cs.getChordStepModifications()) > 0:
            for hd in cs.getChordStepModifications():
                mxDegree = SubElement(mxHarmony, 'degree')
                # types should be compatible
                # TODO: print-object
                mxDegreeValue = SubElement(mxDegree, 'degree-value')
                mxDegreeValue.text = str(hd.degree)
                mxDegreeAlter = SubElement(mxDegree, 'degree-alter')
                if hd.interval is not None:
                    # will return -1 for '-a1'
                    mxDegreeAlter.text = str(hd.interval.chromatic.directed)
                    # TODO: attrGroup: print-style
                    # TODO: attr: plus-minus (yes, no)
                mxDegreeType = SubElement(mxDegree, 'degree-type')
                mxDegreeType.text = str(hd.modType)
                # TODO: attr: text -- alternate display
                # TODO: attrGroup: print-style
            
        self.xmlRoot.append(mxHarmony)
        return mxHarmony

    def setPrintStyleAlign(self, m21Obj, mxObj):
        # print-style-align...
        for src, dst in [(m21Obj._positionDefaultX, 'default-x'),
                     (m21Obj._positionDefaultY, 'default-y'),
                     (m21Obj._positionRelativeX, 'relative-x'),
                     (m21Obj._positionRelativeY, 'relative-y')]:
            if src is not None:
                mxObj.set(dst, str(src))

    def placeInDirection(self, mxObj, m21Obj=None):
        '''
        places the mxObj <element> inside <direction><direction-type>
        '''
        mxDirection = Element('direction')
        mxDirectionType = SubElement(mxDirection, 'direction-type')
        mxDirectionType.append(mxObj)
        if (m21Obj is not None and 
                hasattr(m21Obj, '_positionPlacement') and 
                m21Obj._positionPlacement is not None):
            mxDirectionType.set('placement', m21Obj._positionPlacement)
                
        return mxDirection
    
    def dynamicToXml(self, d):
        '''
        return a nested tag:
        <direction><direction-type><dynamic><ff>
        or whatever...
        
        >>> ppp = dynamics.Dynamic('ppp')
        >>> print('%.2f' % ppp.volumeScalar)
        0.15
        >>> ppp._positionRelativeY = -10

        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxDirection = MEX.dynamicToXml(ppp)
        >>> MEX.dump(mxDirection)
        <direction><direction-type><dynamics default-x="-36" default-y="-80" relative-y="-10"><ppp /></dynamics></direction-type><sound dynamics="19" /></direction>

        appends to score

        '''
        mxDynamics = Element('dynamics')
        if d.value in xmlObjects.DYNAMIC_MARKS:
            mxThisDynamic = SubElement(mxDynamics, d.value)
        else:
            mxThisDynamic = SubElement(mxDynamics, 'other-dynamics')
            mxThisDynamic.text = str(d.value)
        
        self.setPrintStyleAlign(d, mxDynamics)
        # TODO: attrGroup: placement (but done for direction, so okay...
        # TODO: attrGroup: text-decoration
        # TODO: attrGroup: enclosure
        
        # direction todos
        # TODO: offset
        # TODO: editorial-voice-direction
        # TODO: staff

        mxDirection = self.placeInDirection(mxDynamics, d)        
        # sound
        vS = d.volumeScalar
        if vS is not None:
            mxSound = SubElement(mxDirection, 'sound')
            dynamicVolume = int(vS * 127)
            mxSound.set('dynamics', str(dynamicVolume))
        
        self.xmlRoot.append(mxDirection)
        return mxDirection
        
    def segnoToXml(self, segno):
        '''
        returns a segno inside a direction-type inside a direction.

        appends to score
        
        >>> s = repeat.Segno()
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxSegnoDir = MEX.segnoToXml(s)
        >>> MEX.dump(mxSegnoDir)
        <direction><direction-type><segno default-y="20" /></direction-type></direction>
        '''
        mxSegno = Element('segno')
        self.setPrintStyleAlign(segno, mxSegno)
        mxDirection = self.placeInDirection(mxSegno, segno)
        self.xmlRoot.append(mxDirection)
        return mxDirection
        
        
    def codaToXml(self, coda):
        '''
        returns a coda inside a direction-type inside a direction IF coda.useSymbol is
        True; otherwise returns a textExpression...
        
        appends to score
        
        >>> c = repeat.Coda()
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxCodaDir = MEX.codaToXml(c)
        >>> MEX.dump(mxCodaDir)
        <direction><direction-type><coda default-y="20" /></direction-type></direction>   
        
        turn coda.useSymbol to False to get a text expression instead
        
        >>> c.useSymbol = False
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxCodaText = MEX.codaToXml(c)
        >>> MEX.dump(mxCodaText)
        <direction><direction-type><words default-y="20" justify="center">Coda</words></direction-type><offset>0</offset></direction>             
        '''
        if coda.useSymbol:
            mxCoda = Element('coda')
            self.setPrintStyleAlign(coda, mxCoda)
            mxDirection = self.placeInDirection(mxCoda, coda)
            self.xmlRoot.append(mxDirection)
            return mxDirection
        else:
            return self.textExpressionToXml(coda.getTextExpression())
    
    def tempoIndicationToXml(self, ti):
        '''
        returns a <direction> tag for a single tempo indication.

        note that TWO direction tags may be added to xmlroot, the second one
        as a textExpression.... but only the first will be returned.

        >>> mm = tempo.MetronomeMark("slow", 40, note.Note(type='half'))
        
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxDirection = MEX.tempoIndicationToXml(mm)
        >>> MEX.dump(mxDirection)
        <direction><direction-type><metronome parentheses="no"><beat-unit>half</beat-unit><per-minute>40</per-minute></metronome></direction-type><sound><tempo>80.0</tempo></sound></direction>

        In this case, two directions were added to xmlRoot.  Here is the other one:
        
        >>> MEX.dump(MEX.xmlRoot.findall('direction')[1])
        <direction><direction-type><words default-y="45.0" font-weight="bold" justify="left">slow</words></direction-type><offset>0</offset></direction>

    
        >>> mm = tempo.MetronomeMark("slow", 40, duration.Duration(quarterLength=1.5))
        >>> mxDirection = MEX.tempoIndicationToXml(mm)
        >>> MEX.dump(mxDirection)
        <direction><direction-type><metronome parentheses="no"><beat-unit>quarter</beat-unit><beat-unit-dot /><per-minute>40</per-minute></metronome></direction-type><sound><tempo>60.0</tempo></sound></direction>



        >>> mmod1 = tempo.MetricModulation()
        >>> mmod1.oldReferent = .75 # quarterLength
        >>> mmod1.newReferent = 'quarter' # type
        >>> mxDirection = MEX.tempoIndicationToXml(mmod1)
        >>> MEX.dump(mxDirection)
        <direction><direction-type><metronome parentheses="no"><beat-unit>eighth</beat-unit><beat-unit-dot /><beat-unit>quarter</beat-unit></metronome></direction-type></direction>

        >>> mmod1.newReferent = 'longa' # music21 type w/ different musicxml name...
        >>> mxDirection = MEX.tempoIndicationToXml(mmod1)
        >>> MEX.dump(mxDirection)
        <direction><direction-type><metronome parentheses="no"><beat-unit>eighth</beat-unit><beat-unit-dot /><beat-unit>long</beat-unit></metronome></direction-type></direction>
        '''
        # if writing just a sound tag, place an empty words tag in a direction type and then follow with sound declaration
        # storing lists to accommodate metric modulations
        durs = [] # duration objects
        numbers = [] # tempi
        hideNumericalMetro = False # if numbers implicit, hide metronome numbers
        hideNumber = [] # hide the number after equal, e.g., quarter=120, hide 120
        # store the last value necessary as a sounding tag in bpm
        soundingQuarterBPM = False
        if 'MetronomeMark' in ti.classes:
            # will not show a number of implicit
            if ti.numberImplicit or ti.number is None:
                #environLocal.printDebug(['found numberImplict', ti.numberImplicit])
                hideNumericalMetro = True
            else:
                durs.append(ti.referent)
                numbers.append(ti.number)
                hideNumber.append(False)
            # determine number sounding; first, get from numberSounding, then
            # number (if implicit, that is fine); get in terms of quarter bpm
            soundingQuarterBPM = ti.getQuarterBPM()
    
        elif 'MetricModulation' in ti.classes:
            # may need to reverse order if classical style or otherwise
            # may want to show first number
            hideNumericalMetro = False # must show for metric modulation
            for sub in [ti.oldMetronome, ti.newMetronome]:
                hideNumber.append(True) # cannot show numbers in a metric modulation
                durs.append(sub.referent)
                numbers.append(sub.number)
            # soundingQuarterBPM should be obtained from the last MetronomeMark
            soundingQuarterBPM = ti.newMetronome.getQuarterBPM()
    
            #environLocal.printDebug(['found metric modulation', ti, durs, numbers])
        
        mxMetro = Element('metronome')
        for i, d in enumerate(durs):
            # charData of BeatUnit is the type string
            mxSub = Element('beat-unit')
            mxSub.text = typeToMusicXMLType(d.type)
            mxMetro.append(mxSub)
            for _ in range(d.dots):
                mxMetro.append(Element('beat-unit-dot'))
            if len(numbers) > 0:
                if not hideNumber[i]:
                    mxPerMinute = SubElement(mxMetro, 'per-minute') # TODO: font.
                    mxPerMinute.text = str(numbers[0])

        if ti.parentheses:
            mxMetro.set('parentheses', 'yes') # only attribute
        else:
            mxMetro.set('parentheses', 'no') # only attribute        

        mxDirection = self.placeInDirection(mxMetro, ti)
        if soundingQuarterBPM is not None:
            mxSound = SubElement(mxDirection, 'sound')
            mxSoundDynamics = SubElement(mxSound, 'tempo')
            mxSoundDynamics.text = str(soundingQuarterBPM)
        
        if hideNumericalMetro is not None:
            self.xmlRoot.append(mxDirection)
        
        if 'MetronomeMark' in ti.classes:
            if ti.getTextExpression(returnImplicit=False) is not None:
                unused_mxDirectionText = self.textExpressionToXml(
                              ti.getTextExpression(returnImplicit=False))
                
        return mxDirection
    
    def textExpressionToXml(self, te):
        '''Convert a TextExpression to a MusicXML mxDirection type.
        returns a musicxml.mxObjects.Direction object
        '''
        mxWords = Element('words')
        mxWords.text = str(te.content)
        for src, dst in [#(te._positionDefaultX, 'default-x'), 
                         (te.positionVertical, 'default-y'),
    #                      (te._positionRelativeX, 'relative-x'),
    #                      (te._positionRelativeY, 'relative-y')]:
                          (te.enclosure, 'enclosure'),
                          (te.justify, 'justify'),
                          (te.size, 'font-size'),
                          (te.letterSpacing, 'letter-spacing'),
                        ]:
            if src is not None:
                mxWords.set(dst, str(src))
        if te.style is not None and te.style.lower() == 'bolditalic':
            mxWords.set('font-style', 'italic')
            mxWords.set('font-weight', 'bold')
        elif te.style == 'italic':
            mxWords.set('font-style', 'italic')
        elif te.style == 'bold':
            mxWords.set('font-weight', 'bold')
            
        mxDirection = self.placeInDirection(mxWords, te)
        # for complete old compatibility...
        mxOffset = SubElement(mxDirection, 'offset')
        mxOffset.text = str(0)
        
        self.xmlRoot.append(mxDirection)
        return mxDirection
            
    def midmeasureClefToXml(self, clefObj):
        '''
        given a clefObj which is in .elements insert it in self.xmlRoot as
        an attribute if it is not at offset 0.0.
        '''
        if self.offsetInMeasure == 0 and clefObj.offset == 0:
            return
        mxAttributes = Element('attributes')
        mxClef = self.clefToXml(clefObj)
        mxAttributes.append(mxClef)
        self.xmlRoot.append(mxAttributes)
        return mxAttributes
    
    #------------------------------
    # note helpers...
    def lyricToXml(self, l):
        '''
        Translate a music21 :class:`~music21.note.Lyric` object 
        to a <lyric> tag.
        '''
        mxLyric = Element('lyric')
        _setTagTextFromAttribute(l, mxLyric, 'syllabic')
        _setTagTextFromAttribute(l, mxLyric, 'text')
        # TODO: elision
        # TODO: more syllabic
        # TODO: more text
        # TODO: extend
        # TODO: laughing
        # TODO: humming
        # TODO: end-line
        # TODO: end-paragraph
        # TODO: editorial
        if l.identifier is not None:
            mxLyric.set('number', str(l.identifier))
        else:
            mxLyric.set('number', str(l.number))
        # TODO: attr: name - alternate for lyric -- make identifier?
        # TODO: attrGroup: justify
        # TODO: attrGroup: position
        # TODO: attrGroup: placement
        # TODO: attrGroup: color
        # TODO: attrGroup: print-object
        return mxLyric
    
    def beamsToXml(self, beams):
        '''
        Returns a list of <beam> tags 
        from a :class:`~music21.beam.Beams` object
    
        
        >>> a = beam.Beams()
        >>> a.fill(2, type='start')

        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxBeamList = MEX.beamsToXml(a)
        >>> len(mxBeamList)
        2
        >>> for b in mxBeamList:
        ...     MEX.dump(b)
        <beam number="1">begin</beam>
        <beam number="2">begin</beam>        
        '''
        mxBeamList = []
        for beamObj in beams.beamsList:
            mxBeamList.append(self.beamToXml(beamObj))
        return mxBeamList

    def beamToXml(self, beamObject):
        '''
        
        >>> a = beam.Beam()
        >>> a.type = 'start'
        >>> a.number = 1
        
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> b = MEX.beamToXml(a)
        >>> MEX.dump(b)
        <beam number="1">begin</beam>

        >>> a.type = 'continue'
        >>> b = MEX.beamToXml(a)
        >>> MEX.dump(b)
        <beam number="1">continue</beam>
    
        >>> a.type = 'stop'
        >>> b = MEX.beamToXml(a)
        >>> MEX.dump(b)
        <beam number="1">end</beam>
    
        >>> a.type = 'partial'
        >>> a.direction = 'left'
        >>> b = MEX.beamToXml(a)
        >>> MEX.dump(b)
        <beam number="1">backward hook</beam>
    
        >>> a.direction = 'right'
        >>> b = MEX.beamToXml(a)
        >>> MEX.dump(b)
        <beam number="1">forward hook</beam>
    
        >>> a.direction = None
        >>> b = MEX.beamToXml(a)
        Traceback (most recent call last):
        ToMxObjectsException: partial beam defined without a proper direction set (set to None)
    
        >>> a.type = 'crazy'
        >>> b = MEX.beamToXml(a)
        Traceback (most recent call last):
        ToMxObjectsException: unexpected beam type encountered (crazy)
        '''
        mxBeam = Element('beam')
        if beamObject.type == 'start':
            mxBeam.text = 'begin'
        elif beamObject.type == 'continue':
            mxBeam.text = 'continue'
        elif beamObject.type == 'stop':
            mxBeam.text = 'end'
        elif beamObject.type == 'partial':
            if beamObject.direction == 'left':
                mxBeam.text = 'backward hook'
            elif beamObject.direction == 'right':
                mxBeam.text = 'forward hook'
            else:
                raise ToMxObjectsException('partial beam defined without a proper direction set (set to %s)' % beamObject.direction)
        else:
            raise ToMxObjectsException('unexpected beam type encountered (%s)' % beamObject.type)
    
        mxBeam.set('number', str(beamObject.number))
        # not todo: repeater (deprecated)
        # TODO: attr: fan
        # TODO: attr: color group
        return mxBeam

    
    def setRightBarline(self):        
        m = self.stream
        rbSpanners = self.rbSpanners
        rightBarline = self.stream.rightBarline
        if (rightBarline is None and 
                (len(rbSpanners) == 0 or not rbSpanners[0].isLast(m))):
            return
        self.setBarline(rightBarline, 'right')
        
    def setLeftBarline(self):
        m = self.stream
        rbSpanners = self.rbSpanners
        leftBarline = self.stream.leftBarline
        if (leftBarline is None and
                (len(rbSpanners) == 0 or not rbSpanners[0].isFirst(m))):
            return
        self.setBarline(leftBarline, 'left')

    def setBarline(self, barline, position):
        '''
        sets either a left or right barline from a 
        bar.Barline() object or bar.Repeat() object        
        '''        
        if barline is None:
            mxBarline = Element('barline')
        else:
            mxBarline = self.barlineToXml(barline)
        
        mxBarline.set('location', position)
        # TODO: editorial
        # TODO: wavy-line
        # TODO: segno
        # TODO: coda
        # TODO: fermata
        
        if len(self.rbSpanners) > 0: # and self.rbSpanners[0].isFirst(m)???
            mxEnding = Element('ending')
            if position == 'left':
                endingType = 'start'
            else:
                endingType = 'stop'
                mxEnding.set('number', str(self.rbSpanners[0].number))
            mxEnding.set('type', endingType)
            mxBarline.append(mxEnding) # make sure it is after fermata but before repeat.

        if 'Repeat' in barline.classes:
            mxRepeat = self.repeatToXml(barline)
            mxBarline.append(mxRepeat)
        
        # TODO: attr: segno
        # TODO: attr: coda
        # TODO: attr: divisions
        
        self.xmlRoot.append(mxBarline)
        return mxBarline

    def barlineToXml(self, barObject):
        '''
        Translate a music21 bar.Bar object to an mxBar
        while making two substitutions: double -> light-light
        and final -> light-heavy as shown below.
        
        >>> b = bar.Barline('final')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxBarline = MEX.barlineToXml(b)
        >>> MEX.dump(mxBarline)
        <barline><bar-style>light-heavy</bar-style></barline>
        
        >>> b.location = 'right'
        >>> mxBarline = MEX.barlineToXml(b)
        >>> MEX.dump(mxBarline)
        <barline location="right"><bar-style>light-heavy</bar-style></barline>        
        '''
        mxBarline = Element('barline')
        mxBarStyle = SubElement(mxBarline, 'bar-style')
        mxBarStyle.text = barObject.musicXMLBarStyle
        # TODO: mxBarStyle attr: color
        if barObject.location is not None:
            mxBarline.set('location', barObject.location)
        return mxBarline

    def repeatToXml(self, r):
        '''
        returns a <repeat> tag from a barline object.

        >>> b = bar.Repeat(direction='end')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxRepeat = MEX.repeatToXml(b)
        >>> MEX.dump(mxRepeat)
        <repeat direction="backward" />
        
        >>> b.times = 3
        >>> mxRepeat = MEX.repeatToXml(b)
        >>> MEX.dump(mxRepeat)
        <repeat direction="backward" times="3" />
        '''
        mxRepeat = Element('repeat')
        if r.direction == 'start':
            mxRepeat.set('direction', 'forward')
        elif r.direction == 'end':
            mxRepeat.set('direction', 'backward')
    #         elif self.direction == 'bidirectional':
    #             environLocal.printDebug(['skipping bi-directional repeat'])
        else:
            raise bar.BarException('cannot handle direction format:', r.direction)
    
        if r.times != None:
            mxRepeat.set('times', str(r.times))
            
        # TODO: attr: winged
        return mxRepeat

    def setMxAttributesObject(self):
        '''
        creates an <attributes> tag (always? or if needed...)
        '''
        m = self.stream
        self.currentDivisions = defaults.divisionsPerQuarter
        mxAttributes = Element('attributes')
        mxDivisions = SubElement(mxAttributes, 'divisions')
        mxDivisions.text = str(self.currentDivisions)
        if self.transpositionInterval is not None:
            mxAttributes.append(self.intervalToXmlTranspose)
        if m.keySignature is not None:
            mxAttributes.append(self.keySignatureToXml(m.keySignature))
        if m.timeSignature is not None:
            mxAttributes.append(self.timeSignatureToXml(m.timeSignature))
        if m.clef is not None:
            mxAttributes.append(self.clefToXml(m.clef))

        # todo returnType = 'list'
        found = m.getElementsByClass('StaffLayout')
        if len(found) > 0:
            sl = found[0] # assume only one per measure
            mxAttributes.append(self.staffLayoutToXmlStaffDetails(sl)) 

        self.xmlRoot.append(mxAttributes)
        return mxAttributes
    
    def staffLayoutToXmlStaffDetails(self, staffLayout):
        mxStaffDetails = Element('staff-details')
        # TODO: staff-type
        if staffLayout.staffLines is not None:
            mxStaffLines = SubElement(mxStaffDetails, 'staff-lines')
            mxStaffLines.text = str(staffLayout.staffLines)

        if staffLayout.hidden is True:
            mxStaffDetails.set('print-object', 'no')
        else:
            mxStaffDetails.set('print-object', 'yes')
        return mxStaffDetails        
    
    def timeSignatureToXml(self, ts):
        '''
        Returns a single <time> tag from a meter.TimeSignature object.
    
        Compound meters are represented as multiple pairs of beat
        and beat-type elements
    
        
        >>> a = meter.TimeSignature('3/4')
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> b = MEX.timeSignatureToXml(a)
        >>> MEX.dump(b)
        <time><beats>3</beats><beat-type>4</beat-type></time>
        
        >>> a = meter.TimeSignature('3/4+2/4')
        >>> b = MEX.timeSignatureToXml(a)
        >>> MEX.dump(b)
        <time><beats>3</beats><beat-type>4</beat-type><beats>2</beats><beat-type>4</beat-type></time>        
        
        >>> a.setDisplay('5/4')
        >>> b = MEX.timeSignatureToXml(a)
        >>> MEX.dump(b)
        <time><beats>5</beats><beat-type>4</beat-type></time>
        '''
        #mxTimeList = []
        mxTime = Element('time')
        # always get a flat version to display any subivisions created
        fList = [(mt.numerator, mt.denominator) for mt in ts.displaySequence.flat._partition]
        if ts.summedNumerator:
            # this will try to reduce any common denominators into 
            # a common group
            fList = meter.fractionToSlashMixed(fList)
    
        for n, d in fList:
            mxBeats = SubElement(mxTime, 'beats')
            mxBeats.text = str(n)
            mxBeatType = SubElement(mxTime, 'beat-type')
            mxBeatType.text = str(d)
            # TODO: interchangeable
            
        # TODO: choice -- senza-misura
    
        # TODO: attr: interchangeable
        # TODO: attr: symbol
        # TODO: attr: separator
        # TODO: attr: print-style-align
        # TODO: attr: print-object
        return mxTime

    def keySignatureToXml(self, keySignature):
        '''
        returns a key tag from a music21
        key.KeySignature or key.Key object
        
        >>> ks = key.KeySignature(-3)
        >>> ks
        <music21.key.KeySignature of 3 flats>
        
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxKey = MEX.keySignatureToXml(ks)
        >>> MEX.dump(mxKey)
        <key><fifths>-3</fifths></key>

        >>> ks.mode = 'major'
        >>> mxKey = MEX.keySignatureToXml(ks)
        >>> MEX.dump(mxKey)
        <key><fifths>-3</fifths><mode>major</mode></key>
        '''
        seta = _setTagTextFromAttribute
        mxKey = Element('key')
        # TODO: attr: number
        # TODO: attr: print-style
        # TODO: attr: print-object
        
        # choice... non-traditional-key...
        # TODO: key-step
        # TODO: key-alter
        # TODO: key-accidental
        
        # Choice traditional-key
        
        # TODO: cancel
        seta(keySignature, mxKey, 'fifths', 'sharps')
        if keySignature.mode is not None:
            seta(keySignature, mxKey, 'mode')
        # TODO: key-octave
        return mxKey
        
    def clefToXml(self, clefObj):
        '''
        Given a music21 Clef object, return a MusicXML clef 
        tag.
    
        >>> gc = clef.GClef()
        >>> gc
        <music21.clef.GClef>
        >>> MEX = musicxml.m21ToXml.MeasureExporter()
        >>> mxc = MEX.clefToXml(gc)
        >>> MEX.dump(mxc)
        <clef><sign>G</sign></clef>
    
        >>> b = clef.Treble8vbClef()
        >>> b.octaveChange
        -1
        >>> mxc2 = MEX.clefToXml(b)
        >>> MEX.dump(mxc2)
        <clef><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>

        >>> pc = clef.PercussionClef()
        >>> mxc3 = MEX.clefToXml(pc)
        >>> MEX.dump(mxc3)
        <clef><sign>percussion</sign></clef>
        
        Clefs without signs get exported as G clefs with a warning
        
        >>> generic = clef.Clef()
        >>> mxc4 = MEX.clefToXml(generic)
        Clef with no .sign exported; setting as a G clef
        >>> MEX.dump(mxc4)
        <clef><sign>G</sign></clef>
        '''
        # TODO: attr: number
        # TODO: attr: print-style
        # TODO: attr: print-object
        # TODO: attr: number (staff number)
        # TODO: attr: additional
        # TODO: attr: size
        # TODO: attr: after-barline
        mxClef = Element('clef')
        sign = clefObj.sign
        if sign is None:
            print("Clef with no .sign exported; setting as a G clef")
            sign = 'G'
        
        mxSign = SubElement(mxClef, 'sign')
        mxSign.text = sign
        _setTagTextFromAttribute(clefObj, mxClef, 'line')
        if clefObj.octaveChange not in (0, None):
            _setTagTextFromAttribute(clefObj, mxClef, 'clef-octave-change', 'octaveChange')

        return mxClef
        

    def intervalToXmlTranspose(self, i=None):
        '''
        >>> ME = musicxml.m21ToXml.MeasureExporter()
        >>> i = interval.Interval('P5')
        >>> mxTranspose = ME.intervalToXmlTranspose(i)
        >>> ME.dump(mxTranspose)
        <transpose><diatonic>4</diatonic><chromatic>7</chromatic></transpose>
        
        >>> i = interval.Interval('A13')
        >>> mxTranspose = ME.intervalToXmlTranspose(i)
        >>> ME.dump(mxTranspose)
        <transpose><diatonic>19</diatonic><chromatic>10</chromatic><octave-shift>1</octave-shift></transpose>

        >>> i = interval.Interval('-M6')
        >>> mxTranspose = ME.intervalToXmlTranspose(i)
        >>> ME.dump(mxTranspose)
        <transpose><diatonic>-5</diatonic><chromatic>-9</chromatic></transpose>
        '''
        # TODO: number attribute (staff number)
        # TODO: double empty attribute
        if i is None:
            i = self.transpositionInterval
        rawSemitones = i.chromatic.semitones # will be directed
        octShift = 0
        if abs(rawSemitones) > 12:
            octShift, semitones = divmod(rawSemitones, 12)
        else:
            semitones = rawSemitones
        rawGeneric = i.diatonic.generic.directed
        if octShift != 0:
            # need to shift 7 for each octave; sign will be correct
            generic = rawGeneric + (octShift * 7)
        else:
            generic = rawGeneric
    
        mxTranspose = Element('transpose')
        mxDiatonic = SubElement(mxTranspose, 'diatonic')
    
        # must implement the necessary shifts
        if rawGeneric > 0:
            mxDiatonic.text = str(generic - 1)
        elif rawGeneric < 0:
            mxDiatonic.text = str(generic + 1)

        mxChromatic = SubElement(mxTranspose, 'chromatic')
        mxChromatic.text = str(semitones)
    
        if octShift != 0:
            mxOctaveChange = SubElement(mxTranspose, 'octave-shift')
            mxOctaveChange.text = str(octShift)
        
        return mxTranspose


    def setMxPrint(self):
        m = self.stream
        # print objects come before attributes
        # note: this class match is a problem in cases where the object is created in the module itself, as in a test. 
    
        # do a quick search for any layout objects before searching individually...
        foundAny = m.getElementsByClass('LayoutBase')
        if len(foundAny) == 0:
            return

        mxPrint = None        
        found = m.getElementsByClass('PageLayout')
        if len(found) > 0:
            pl = found[0] # assume only one per measure
            mxPrint = self.pageLayoutToXmlPrint(pl)
        found = m.getElementsByClass('SystemLayout')
        if len(found) > 0:
            sl = found[0] # assume only one per measure
            if mxPrint is None:
                mxPrint = self.systemLayoutToXmlPrint(sl)
            else:
                self.systemLayoutToXmlPrint(sl, mxPrint)
        found = m.getElementsByClass('StaffLayout')
        if len(found) > 0:
            sl = found[0] # assume only one per measure
            if mxPrint is None:
                mxPrint = self.staffLayoutToXmlPrint(sl)
            else:
                self.staffLayoutToXmlPrint(sl, mxPrint)
        # TODO: measure-layout
        # TODO: measure-numbering
        # TODO: part-name-display
        # TODO: part-abbreviation-display

        # TODO: attr: blank-page
        # TODO: attr: page-number

        if mxPrint is not None:
            self.xmlRoot.append(mxPrint)

    def staffLayoutToXmlPrint(self, staffLayout, mxPrint=None):
        if mxPrint is None:
            mxPrint = Element('print')
        mxStaffLayout = self.staffLayoutToXmlStaffLayout(staffLayout)
        mxPrint.append(mxStaffLayout)
        return mxPrint

        
    def setMxAttributes(self):
        '''
        sets the attributes (x=y) for a measure,
        that is, number, and layoutWidth
        
        Does not create the <attributes> tag. That's elsewhere...
        
        '''
        m = self.stream
        self.xmlRoot.set('number', m.measureNumberWithSuffix())
        # TODO: attr: implicit
        # TODO: attr: non-controlling
        if m.layoutWidth is not None:
            _setAttributeFromAttribute(m, self.xmlRoot, 'width', 'layoutWidth')
        
    def setRbSpanners(self):
        self.rbSpanners = self.spannerBundle.getBySpannedElement(
                                self.stream).getByClass('RepeatBracket')
        
    def setTranspose(self):
        if self.parent is None:
            return
        if self.parent.stream is None:
            return
        if self.parent.stream.atSoundingPitch is True:
            return

        m = self.stream
        self.measureOffsetStart = m.getOffsetBySite(self.parent.stream)

        instSubStream = self.parent.instrumentStream.getElementsByOffset(
                    self.measureOffsetStart,
                    self.measureOffsetStart + m.duration.quarterLength,
                    includeEndBoundary=False)        
        if len(instSubStream) == 0:
            return
        
        instSubObj = instSubStream[0]
        if instSubObj.transposition is None:
            return
        self.transpositionInterval = instSubObj.transposition
        # do here???
        #self.mxTranspose = self.intervalToMXTranspose()



#-------------------------------------------------------------------------------
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
            

class Test(unittest.TestCase):

    def runTest(self):
        pass

    def testBasic(self):
        pass

    def xtestFindOneError(self):
        from music21 import corpus, converter

        b = corpus.parse('schoenberg')

        SX = ScoreExporter(b)
        mxScore = SX.parse()
        for x in mxScore.findall('part'):
            print(x)
            for y in x:
                print(y)
                for z in y:
                    print(z)
                    for w in z:
                        print(w)
                        for v in w:
                            print(v)
                            SX.dump(v)
                            for u in v:
                                print(u)
                                SX.dump(u)
        

    def xtestSimple(self):
        from xml.etree.ElementTree import ElementTree
        from music21 import corpus, converter
        import codecs
        import difflib
        
        b = converter.parse(corpus.getWorkList('cpebach')[0], format='musicxml', forceSource=True)
        #b.show('text')
        #n = b.flat.notes[0]
        #print(n.expressions)
        #return

        SX = ScoreExporter(b)
        mxScore = SX.parse()
        
        indent(mxScore)
        
        sio = six.BytesIO()
        
        et = ElementTree(mxScore)
        sio.write(b'''<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE score-partwise\n  PUBLIC '-//Recordare//DTD MusicXML 2.0 Partwise//EN'\n  'http://www.musicxml.org/dtds/partwise.dtd'>\n''')
        et.write('/Users/Cuthbert/Desktop/s.xml', encoding="utf-8", xml_declaration=True)
        et.write(sio, encoding="utf-8", xml_declaration=False)
        v = sio.getvalue()
        sio.close()

        v = v.decode('utf-8')
        v = v.replace(' />', '/>') # normalize

        #b2 = converter.parse(v)
        fp = b.write('musicxml')
        print(fp)
        return
        with codecs.open(fp, encoding='utf-8') as f:
            v2 = f.read()
        differ = list(difflib.ndiff(v.splitlines(), v2.splitlines()))
        for i, l in enumerate(differ):
                if l.startswith('-') or l.startswith('?') or l.startswith('+'):
                    print(l)
                #for j in range(i-1,i+1):
                #    print(differ[j])
                #print('------------------')


if __name__ == '__main__':
    import music21
    #music21.mainTest('docTestOnly')
    music21.mainTest(Test) #, runTest='testSimple')