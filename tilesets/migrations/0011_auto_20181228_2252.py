# Generated by Django 2.0.9 on 2018-12-28 22:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("tilesets", "0010_auto_20181228_2250")]

    operations = [
        migrations.AlterField(
            model_name="tileset",
            name="datatype",
            field=models.TextField(blank=True, default="unknown", null=True),
        )
    ]
