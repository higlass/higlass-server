# Generated by Django 3.1 on 2021-11-19 19:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tilesets', '0013_auto_20211119_1935'),
    ]

    operations = [
        migrations.AlterField(
            model_name='viewconf',
            name='higlassVersion',
            field=models.CharField(blank=True, default='', max_length=16, null=True),
        ),
    ]
