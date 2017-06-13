import cloudstorage
import datetime
import heapq
import logging
import pickle
import uuid
import sys
import web
import os

from pipeline import Pipeline

from web import config
from web import rutil
from web import rtime
from web.base import BaseView, Route

# Report Generators

class ReportGenerator(object):

    __abstract__ = True
    reportName = None
    description = None
    pipelineCls = None

    @classmethod
    def getParameters(self):
        return []

    def __init__(self, reportId):
        self.reportId = reportId

    def getInfo(self):
        return self.reportName

    def getPipeline(self):
        return self.pipelineCls(outputFile=self.reportId)

class StartEndReportGenerator(ReportGenerator):

    __abstract__ = True
    pipelineCls = None

    @classmethod
    def getParameters(self):
        now = datetime.datetime.now()
        start = rtime.toLocal(
            datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0)
        )
        return [
            {
                'field': 'startDate',
                'name': "Start Date",
                'type': 'date',
                'default': start,
            },
            {
                'field': 'endDate',
                'name': "End Date",
                'type': 'date',
                'default': now,
            },
        ]

    def __init__(self, reportId, startDate, endDate):
        ReportGenerator.__init__(self, reportId)
        self.startDate = startDate
        self.endDate = endDate + datetime.timedelta(hours=23, minutes=59)
        self.startDateTarget = rtime.toTarget(self.startDate)
        self.endDateTarget = rtime.toTarget(self.endDate)
        self.validateStartEnd()

    def validateStartEnd(self):
        if (self.endDate - self.startDate) > datetime.timedelta(days=1000):
            raise ValueError('TIME PERIOD TOO LONG!!')

    def getInfo(self):
        return "%s from %s to %s" % (
            self.reportName,
            self.startDateTarget.strftime('%Y-%m-%d'),
            self.endDateTarget.strftime('%Y-%m-%d'),
        )

    def getPipeline(self):
        return self.pipelineCls(
            startDate=self.startDate,
            endDate=self.endDate,
            outputFile=self.reportId,
        )

# Utility Pipelines

class BasePipeline(Pipeline):

    __abstract__ = True

    def __init__(self, *args, **kwargs):
        Pipeline.__init__(self, *args, **kwargs)
        targetVersion = os.environ['CURRENT_VERSION_ID'].split(".")[0]
        targetModule = config.CONFIG['PIPELINE']['MODULE']
        self.target = "%s.%s" % (targetVersion, targetModule)

class BaseReportPipeline(BasePipeline):

    __abstract__ = True
    delta = datetime.timedelta(hours=16)

    def cleanRow(self, row):
        cleanRow = []
        for col in row:
            if isinstance(col, unicode):
                col = '"%s"' % col.replace('"', '')
            elif isinstance(col, datetime.datetime):
                col = rtime.formatTime(col)
            elif col is None:
                col = ""
            else:
                col = str(col)
            cleanRow.append(col)
        joinedRow = ",".join(cleanRow)
        return joinedRow.encode('utf-8')

    # def formatTime(self, date):
    #     date = rtime.toTarget(date)
    #     return date.strftime("%Y-%m-%d %H:%M:%S")

    def segmentInterval(self, startDate, endDate, **kwargs):
        subStart = startDate
        while subStart < endDate:
            subEnd = min(endDate, subStart + self.delta)
            yield subStart, subEnd
            subStart += self.delta

    def writeRows(self, rows, targetFilename):
        bucket = config.CONFIG['PIPELINE']['BUCKET']
        path = "/%s/%s" % (bucket, targetFilename)
        with cloudstorage.open(path, 'w', 'text/csv') as outfile:
            for row in rows:
                print >> outfile, self.cleanRow(row)
        return path

class CombineCsvs(BaseReportPipeline):

    def run(self, header, targetFilename, *sourceFilenames):
        bucket = config.CONFIG['PIPELINE']['BUCKET']
        targetPath = "/%s/%s" % (bucket, targetFilename)
        with cloudstorage.open(
                targetPath, 'w', 
                content_type='text/csv',
            ) as outfile:
            print >> outfile, str(",".join(header))
            for sourceFilename in sourceFilenames:
                with cloudstorage.open(sourceFilename, 'r') as infile:
                    for line in infile:
                        outfile.write(line)
        return targetFilename

class CombineVariableHeaderCsvs(BaseReportPipeline):

    def run(self, targetFilename, *sourceFilenames):
        self.writeRows(self.getRows(sourceFilenames), targetFilename)

        # TODO: there could be a better abstracted way to store this header...
        from web.reporting.reportingModels import ReportLog
        ReportLog.putHeader(targetFilename, self.masterHeader)

    def getRows(self, sourceFilenames):
        self.masterHeader = []
        masterHeaderMap = {}
        for sourceFilename in sourceFilenames:
            with cloudstorage.open(sourceFilename, 'r') as infile:
                reader = rutil.unicodeCsvReader(infile)
                currentHeader = None
                for row in reader:
                    if currentHeader is None:
                        currentHeader = []
                        for key in row:
                            if key not in masterHeaderMap:
                                masterHeaderMap[key] = len(masterHeaderMap)
                                self.masterHeader.append(key)
                            currentHeader.append(masterHeaderMap[key])
                    else:
                        outputRow = [""] * len(masterHeaderMap)
                        for loc, val in zip(currentHeader, row):
                            outputRow[loc] = val
                        yield outputRow

class ConcatenateLists(BaseReportPipeline):

    def run(self, *sublists):
        combined = []
        for sublist in sublists:
            combined += sublist
        return combined

class ReporterPipeline(BaseReportPipeline):

    def getRows(self, **kwargs):
        return []

    def run(self, **kwargs):
        return self.writeRows(self.getRows(**kwargs), uuid.uuid4())

class SegmentingPipeline(ReporterPipeline):

    header = []

    def run(self, mode='disburse', **kwargs):
        if mode == 'disburse':
            segments = []
            for segment in self.getSegments(**kwargs):
                segments.append((yield segment))
            logging.info(len(segments))
            yield self.getCombiner(
                kwargs.get('outputFile'),
                segments,
            )
        else:
            tmpFile = ReporterPipeline.run(self, **kwargs)
            yield ReturnValue(tmpFile)
    
    def getCombiner(self, outputFile, segments):
        return CombineCsvs(
            self.header, 
            outputFile,
            *segments
        )

    def getSegments(self, **kwargs):
        # This should yield a number of pipelines whose result 
        # is a file to concatenate
        raise NotImplemented

class ExporterPipeline(SegmentingPipeline):
    
    def getSegments(self, **kwargs):
        segments = []
        for subStart, subEnd in self.segmentInterval(**kwargs):
            newArgs = dict(kwargs)
            newArgs['mode'] = 'run'
            newArgs['startDate'] = subStart
            newArgs['endDate'] = subEnd
            yield self.__class__(**newArgs)

class ChunkedMongoExporterPipeline(ExporterPipeline):

    chunkSizeLimit = 5000

    def getRows(self, **kwargs):
        query, sort, mongoCls = self.getQuery(**kwargs)
        for item in mongoCls.queryIter(query, sort=sort):
            yield self.export(item)

    def getQuery(self, **kwargs):
        raise NotImplemented

    def export(self, item, **kwargs):
        raise NotImplemented

    def segmentInterval(self, startDate, endDate, **kwargs):
        query, sort, mongoCls = self.getQuery(startDate=startDate, endDate=endDate, **kwargs)
        count = mongoCls.queryCount(query, limit=self.chunkSizeLimit)
        if count == 0:
            return []
        elif count < self.chunkSizeLimit:
            return [(startDate, endDate)]
        else:
            midPoint = startDate + ((endDate - startDate) / 2)
            left = self.segmentInterval(startDate, midPoint, **kwargs)
            right = self.segmentInterval(midPoint, endDate, **kwargs)
            return left + right

class ChunkedTaskletExporterPipeline(ExporterPipeline):

    def getRows(self, **kwargs):
        query = self.getQuery(**kwargs)
        for items in rutil.ndbIterateChunked(query, 50, use_cache=False):
            futures = [self.export(item) for item in items]
            for future in futures:
                yield future.get_result()

    def getQuery(self, **kwargs):
        raise NotImplemented

class ReturnValue(BaseReportPipeline):

    def run(self, value):
        return value

class ReturnValues(BaseReportPipeline):

    def run(self, *values):
        return values

from pipeline.handlers import _APP as PIPELINE_APP