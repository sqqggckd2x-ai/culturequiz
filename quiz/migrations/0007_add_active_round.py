"""Add active_round and active_round_started_at fields to Game

Created to reflect model changes made in code.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0006_game_active_question_started_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='active_round',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='quiz.round'),
        ),
        migrations.AddField(
            model_name='game',
            name='active_round_started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время старта активного раунда'),
        ),
    ]
