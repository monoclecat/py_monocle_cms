# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-08-01 19:27
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('py_monocle_cms', '0004_auto_20170801_1822'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='page',
            name='abstract',
        ),
    ]