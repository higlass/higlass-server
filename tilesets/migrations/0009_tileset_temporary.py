# Generated by Django 2.0.9 on 2018-12-13 22:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tilesets', '0008_auto_20181129_1304'),
    ]

    operations = [
        migrations.AddField(
            model_name='tileset',
            name='temporary',
            field=models.BooleanField(default=False),
        ),
    ]
