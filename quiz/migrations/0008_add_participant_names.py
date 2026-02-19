"""Add last_name/first_name/middle_name to Participant

Created to reflect model changes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0007_add_active_round'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='last_name',
            field=models.CharField(max_length=150, null=True, blank=True, verbose_name='Фамилия'),
        ),
        migrations.AddField(
            model_name='participant',
            name='first_name',
            field=models.CharField(max_length=150, null=True, blank=True, verbose_name='Имя'),
        ),
        migrations.AddField(
            model_name='participant',
            name='middle_name',
            field=models.CharField(max_length=150, null=True, blank=True, verbose_name='Отчество'),
        ),
    ]
