"""
Utilities for querying the Dept of Ed's collegescorecard api

The API, released 2015-09-12, requires a key, which you can get
from https://api.data.gov/signup/
- API repo:
    https://github.com/18F/open-data-maker
- collegechoice repo:
    https://github.com/18F/college-choice
- raw data:
    https://s3.amazonaws.com/ed-college-choice-public/CollegeScorecard_Raw_Data.zip
- api_key usage:
    https://api.data.gov/docs/api-key/
"""
from __future__ import print_function
import os
import sys
import json
import datetime
from copy import copy
from decimal import Decimal

import requests

from paying_for_college.models import ConstantCap

try:
    LATEST_YEAR = ConstantCap.objects.get(slug='apiYear').value
except:  # pragma: no cover
    LATEST_YEAR = 2013
try:
    LATEST_SALARY_YEAR = ConstantCap.objects.get(slug='salaryYear').value
except:  # pragma: no cover
    LATEST_SALARY_YEAR = 2011

try:
    API_KEY = os.getenv('ED_API_KEY')
except:  # pragma: no cover
    API_KEY = '0123456789' * 4
API_ROOT = "https://api.data.gov/ed/collegescorecard/v1"
SCHOOLS_ROOT = "{0}/schools".format(API_ROOT)
# SCHEMA_ROOT = "{0}/data.json".format(API_ROOT)
PAGE_MAX = 100  # the max page size allowed as of 2015-09-14

MODEL_MAP = {
    'ope6_id': 'ope6_id',
    'ope8_id': 'ope8_id',
    '{0}.student.size'.format(LATEST_YEAR): 'enrollment',
    'school.accreditor': 'accreditor',
    'school.school_url': 'url',
    'school.degrees_awarded.predominant': 'degrees_predominant',  # data guide says this is INDICATORGROUP
    'school.degrees_awarded.highest': 'degrees_highest',
    'school.ownership': 'ownership',
    'school.main_campus': 'main_campus',
    # 'school.branches',  # ??
    'school.online_only': 'online_only',
    'school.operating': 'operating',
    'school.under_investigation': 'under_investigation',
    'school.zip': 'zip5',
    '{0}.completion.completion_rate_4yr_150nt_pooled'.format(LATEST_YEAR): 'grad_rate_4yr',
    '{0}.completion.completion_rate_less_than_4yr_150nt_pooled'.format(LATEST_YEAR): 'grad_rate_lt4',
    '{0}.repayment.repayment_cohort.3_year_declining_balance'.format(LATEST_YEAR): 'repay_3yr',  # NEW
    '{0}.repayment.3_yr_default_rate'.format(LATEST_YEAR): 'default_rate',
    '{0}.aid.median_debt_suppressed.overall'.format(LATEST_YEAR): 'median_total_debt',
    '{0}.aid.median_debt_suppressed.completers.monthly_payments'.format(LATEST_YEAR): 'median_monthly_debt',  # NEW
    '{0}.cost.avg_net_price.overall'.format(LATEST_YEAR): 'avg_net_price',
    '{0}.cost.tuition.out_of_state'.format(LATEST_YEAR): 'tuition_out_of_state',
    '{0}.cost.tuition.in_state'.format(LATEST_YEAR): 'tuition_in_state',
    '{0}.earnings.10_yrs_after_entry.median'.format(LATEST_SALARY_YEAR): 'median_annual_pay',
}

# JSON_MAP = {
#     # '{0}.student.retention_rate.four_year.full_time'.format(LATEST_YEAR): 'RETENTRATE',
#     # '{0}.student.retention_rate.lt_four_year.full_time'.format(LATEST_YEAR): 'RETENTRATELT4',  # NEW
# }

BASE_FIELDS = [
    'id',
    'ope6_id',
    # 'ope8_id',
    'school.name',
    'school.city',
    'school.state',
    'school.zip',
    'school.accreditor',
    'school.school_url',
    'school.degrees_awarded.predominant',
    'school.degrees_awarded.highest',
    'school.ownership',
    'school.main_campus',
    'school.branches',
    'school.online_only',
    'school.operating',
    'school.under_investigation',
]

YEAR_FIELDS = [
    'completion.completion_rate_4yr_150nt_pooled',
    'completion.completion_rate_less_than_4yr_150nt_pooled',
    'cost.attendance.academic_year',
    'cost.attendance.program_year',
    'cost.tuition.in_state',
    'cost.tuition.out_of_state',
    'cost.tuition.program_year',
    'cost.avg_net_price.overall',
    'student.fafsa_sent.2_college_allyrs',
    'student.fafsa_sent.3_college_allyrs',
    'student.fafsa_sent.4_college_allyrs',
    'student.fafsa_sent.5plus_college_allyrs',
    'student.fafsa_sent.overall',
    'student.fafsa_sent.1_college',
    'student.fafsa_sent.2_colleges',
    'student.fafsa_sent.3_college',  # yes, should be 'colleges'
    'student.fafsa_sent.4_colleges',
    'student.fafsa_sent.5_or_more_colleges',
    'student.fafsa_sent.2_college_allyrs',
    'student.fafsa_sent.3_college_allyrs',
    'student.fafsa_sent.4_college_allyrs',
    'student.fafsa_sent.5plus_college_allyrs',
    'student.size',
    'student.enrollment.all',  # blank for many schools
    'admissions.admission_rate.overall',
    'admissions.admission_rate.by_ope_id',
    'student.retention_rate.four_year.full_time',
    'student.retention_rate.lt_four_year.full_time',
    'student.retention_rate.four_year.part_time',
    'student.retention_rate.lt_four_year.part_time',
    'student.demographics.veteran',  # blank for many schools
    'aid.federal_loan_rate',
    'aid.cumulative_debt.number',
    'aid.cumulative_debt.90th_percentile',
    'aid.cumulative_debt.75th_percentile',
    'aid.cumulative_debt.25th_percentile',
    'aid.cumulative_debt.10th_percentile',
    'aid.median_debt_suppressed.overall',
    'aid.median_debt_suppressed.completers.overall',
    'aid.median_debt_suppressed.completers.monthly_payments',
    'aid.students_with_any_loan',
    'repayment.3_yr_repayment_suppressed.overall',
    'repayment.repayment_cohort.1_year_declining_balance',
    'repayment.1_yr_repayment.completers',
    'repayment.1_yr_repayment.noncompleters',
    'repayment.repayment_cohort.3_year_declining_balance',
    'repayment.3_yr_repayment.completers',
    'repayment.3_yr_repayment.noncompleters',
    'repayment.repayment_cohort.5_year_declining_balance',
    'repayment.5_yr_repayment.completers',
    'repayment.5_yr_repayment.noncompleters',
    'repayment.repayment_cohort.7_year_declining_balance',
    'repayment.7_yr_repayment.completers',
    'repayment.7_yr_repayment.noncompleters',
    'earnings.6_yrs_after_entry.working_not_enrolled.mean_earnings',
    'earnings.6_yrs_after_entry.median',
    'earnings.6_yrs_after_entry.percent_greater_than_25000',
    'earnings.7_yrs_after_entry.mean_earnings',
    'earnings.7_yrs_after_entry.percent_greater_than_25000',
    'earnings.8_yrs_after_entry.mean_earnings',
    'earnings.8_yrs_after_entry.median_earnings',
    'earnings.8_yrs_after_entry.percent_greater_than_25000',
    'earnings.9_yrs_after_entry.mean_earnings',
    'earnings.9_yrs_after_entry.percent_greater_than_25000',
    'earnings.10_yrs_after_entry.working_not_enrolled.mean_earnings',
    'earnings.10_yrs_after_entry.median',
    'earnings.10_yrs_after_entry.percent_greater_than_25000'
]


def build_field_string(YEAR=LATEST_YEAR):
    """assemble fields for an api query"""
    fields = BASE_FIELDS + ['{0}.{1}'.format(YEAR, field)
                            for field in YEAR_FIELDS]
    field_string = ",".join([field for field in fields])
    return field_string


# def get_schools_by_page(year, page=0):
#     """get a page of schools for a single year as dict"""
#     field_string = build_fields_string(year)
#     url = "{0}?api_key={1}&page={2}&per_page={3}&fields={4}".format(SCHOOLS_ROOT,
#                                                            API_KEY,
#                                                            page,
#                                                            PAGE_MAX,
#                                                            field_string)
#     data = json.loads(requests.get(url).text)
#     return data


def search_by_school_name(name):
    """search api by school name, return school name, id, city, state"""
    fields = "id,school.name,school.city,school.state"
    url = "{0}?api_key={1}&school.name={2}&fields={3}".format(SCHOOLS_ROOT,
                                                          API_KEY,
                                                          name,
                                                          fields)
    data = requests.get(url).json()['results']
    return data


# def get_all_school_ids():
#     """traverse pages, assemble all school ids and names and output as json."""
#     collector = {0}
#     url = '{0}?api_key={1}&fields=id,school.name'.format(SCHOOLS_ROOT, API_KEY)
#     for page in range(1, 391):
#         next_url = "{0}&page={1}".format(url, page)
#         nextdata = json.loads(requests.get(next_url).text)
#         for entry in nextdata['results']:
#             collector[entry['id']] = entry['school.name']
#     with open('school_ids.json', 'w') as f:
#         f.write(json.dumps(collector))


# def unpack_alias(alist, school):
#     "create alias objects from a list of aliases"
#     for alias in alist:
#         new, created = Alias.objects.get_or_create(alias=alias,
#                                                    institution=school,
#                                                    defaults={'is_primary':
#                                                              False})
#     #example from Penn's alias string
#     ALIST = [
#         'Penn',
#         'U of PA',
#         'U-Penn',
#         'U of P',
#         'Pennsylvania',
#         'UPenn',
#         'Pennsylvania University',
#         'Wharton',
#         'Wharton School of Business']


def calculate_group_percent(group1, group2):
    """calculates one group's percentage of a two-group total"""
    if group1 + group2 == 0:
        return 0
    else:
        return round(group1 * 100.0 / (group1 + group2), 2)


# USF = 137351
def get_repayment_data(school_id, year):
    """return metric on student debt repayment"""
    school_id = "{0}".format(school_id)
    entrylist = [
        '{0}.repayment.3_yr_repayment_suppressed.overall',
        '{0}.repayment.repayment_cohort.1_year_declining_balance',
        '{0}.repayment.1_yr_repayment.completers',
        '{0}.repayment.1_yr_repayment.noncompleters',
        '{0}.repayment.repayment_cohort.3_year_declining_balance',
        '{0}.repayment.3_yr_repayment.completers',
        '{0}.repayment.3_yr_repayment.noncompleters',
        '{0}.repayment.repayment_cohort.5_year_declining_balance',
        '{0}.repayment.5_yr_repayment.completers',
        '{0}.repayment.5_yr_repayment.noncompleters',
        '{0}.repayment.repayment_cohort.7_year_declining_balance',
        '{0}.repayment.7_yr_repayment.completers',
        '{0}.repayment.7_yr_repayment.noncompleters']
    fields = ",".join([entry.format(year) for entry in entrylist])
    url = "{0}?id={1}&api_key={2}&fields={3}".format(SCHOOLS_ROOT,
                                                     school_id,
                                                     API_KEY,
                                                     fields)
    data = requests.get(url).json()['results'][0]
    repay_completers = data['{0}.repayment.5_yr_repayment.completers'.format(year)]
    repay_non = data['{0}.repayment.5_yr_repayment.noncompleters'.format(year)]
    data['completer_repayment_rate_after_5_yrs'] = calculate_group_percent(repay_completers, repay_non)
    return data
