# Generated by Django 4.2.7 on 2024-01-24 08:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bom', '0002_alter_partsstructurechangeset_table_and_more'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='partsstructure',
            table='bom_parts_structure',
        ),
    ]
