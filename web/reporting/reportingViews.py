import urllib
import pipeline
import cloudstorage
import datetime
import importlib
import uuid

from web import api
from web import config
from web import validate
from web import rutil
from web.admin import requireRole
from web.base import BaseView, Route, RedirectException
from web.models import *
from web.reporting.reportingModels import *
from web.pipelines import ReportGenerator

class ReportView(BaseView):

    @Route('/web-admin/reports/')
    def listReports(self):
        requireRole('admin')
        reportClasses = self._getReportClasses()
        history = ReportLog.query().order(-ReportLog.run).fetch(20)
        return flask.render_template('web-admin/listReports.jinja2', 
            reportClasses=reportClasses,
            history=history,
        )

    @Route('/web-admin/reports/run/<reportName>/')
    def runReport(self, reportName):
        requireRole('admin')
        reportClasses = self._getReportClasses()
        reportClass = self._getReportClass(reportName)
        parameters = reportClass.getParameters()
        if parameters:
            return flask.render_template('web-admin/reportParameters.jinja2', 
                reportName=reportName,
                parameters=parameters,
            )
        else:
            return self._runReport(reportClass, {})

    @Route('/web-admin/reports/run/<reportName>/with-params/', methods=['GET', 'POST'])
    def runReportWithParameters(self, reportName):
        requireRole('admin')
        reportClass = self._getReportClass(reportName)
        parameters = reportClass.getParameters()
        kwargs = {}
        for parameter in parameters:
            if parameter['type'] == 'date':
                value = validate.get(
                    parameter['field'],
                    validate.ParseDateField(True),
                )
            elif parameter['type'] == 'bool':
                value = validate.get(
                    parameter['field'],
                    validate.ParseBool(),
                )
            else:
                value = validate.get(parameter['field'])
            kwargs[parameter['field']] = value
        return self._runReport(reportClass, kwargs)

    @Route('/web-admin/reports/download/<reportKey>/')
    def reportDownload(self, reportKey):
        requireRole('admin')
        report = ndb.Key(urlsafe=reportKey).get()
        rows = self._generateRows(report)
        response = flask.Response(rows, mimetype='text/csv')
        response.headers['Content-Disposition'] = """attachment; filename="%s.csv";""" % (report.reportId)
        return response

    @Route('/web-admin/reports/<reportKey>/')
    def reportInfo(self, reportKey):
        requireRole('admin')
        report = ndb.Key(urlsafe=reportKey).get()
        return flask.render_template('web-admin/reportInfo.jinja2', report=report)

    @Route('/web-admin/reports/preview/<reportKey>/')
    def reportPreview(self, reportKey):
        requireRole('admin')
        report = ndb.Key(urlsafe=reportKey).get()
        rows = self._generateTable(report)
        response = flask.Response(rows)
        return response

    @Route('/web-admin/reports/status/<reportKey>/')
    def reportStatus(self, reportKey):
        requireRole('admin')
        report = ndb.Key(urlsafe=reportKey).get()
        return flask.jsonify(report.getStatus())

    def _generateRows(self, report):
        header = report.getHeader()
        print header
        if header:
            yield ",".join(header) + "\n"
        gcsPath = report.getCloudstoragePath()
        with cloudstorage.open(gcsPath, 'r') as infile:
            for line in infile:
                yield line

    def _generateTable(self, report):
        yield """
            <style type="text/css">
                table {
                    border-top: 1px solid #ccc;
                    border-left: 1px solid #ccc;
                }
                td {
                    border-right: 1px solid #ccc;
                    border-bottom: 1px solid #ccc;
                    padding: 2px 5px;
                }
                tr:first-child {
                    background: lightblue;
                    border-color: white;
                }
                body {
                    padding: 0;
                    margin: 0;
                }
            </style>
        """
        yield """<table>"""
        header = report.getHeader()
        if header:
            yield """<tr>"""
            yield "".join(["""<td>%s</td>""" % col for col in header])
            yield """</tr>"""
        gcsPath = report.getCloudstoragePath()
        with cloudstorage.open(gcsPath, 'r') as infile:
            reader = rutil.unicodeCsvReader(infile)
            for row in reader:
                yield """<tr>"""
                yield "".join(["""<td>%s</td>""" % col for col in row])
                yield """</tr>"""
        yield """</table>"""

    def _getReportClass(self, reportName):
        reportClasses = self._getReportClasses()
        reportClass = [x for x in reportClasses if x.reportName == reportName][0]
        return reportClass

    def _getReportClasses(self):
        module = importlib.import_module(config.CONFIG['PIPELINE']['REPORT_MODULE'])
        return list(rutil.getSubclasses(module, ReportGenerator))

    def _runReport(self, reportClass, kwargs):
        reportId = reportClass.reportName + ":" + str(uuid.uuid4())
        try:
            reportGenerator = reportClass(reportId, **kwargs)
        except ValueError as e:
            flask.abort(400, str(e))

        pipeline = reportGenerator.getPipeline()
        pipeline.start(
            queue_name=config.CONFIG['PIPELINE']['QUEUE'],
        )

        reportLog = ReportLog(
            pipelineId=pipeline.pipeline_id,
            reportId=reportGenerator.reportId,
            reportName=reportGenerator.reportName,
            reportInfo=reportGenerator.getInfo(),
        )
        reportLog.put()

        return flask.redirect(reportLog.getInfoUrl())