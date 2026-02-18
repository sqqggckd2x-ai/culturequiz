"""Add active_question and accepting_answers fields to Game

Generated manually to match deployed state.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0004_alter_answer_options_alter_game_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='active_question',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='quiz.question'),
        ),
        migrations.AddField(
            model_name='game',
            name='accepting_answers',
            field=models.BooleanField(default=False, verbose_name='Принимаются ответы'),
        ),
    ]
