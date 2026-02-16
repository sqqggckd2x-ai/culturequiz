from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db import transaction
from . import models


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'is_active', 'mode', 'created_at', 'manage_link')
    search_fields = ('title', 'description')
    actions = ('activate_selected_games', 'duplicate_games')

    def manage_link(self, obj):
        try:
            url = reverse('admin_panel:manage_game', args=[obj.id])
        except Exception:
            url = f'/admin/game/{obj.id}/manage/'
        return mark_safe(f'<a class="button" href="{url}">Перейти в панель управления</a>')

    manage_link.short_description = 'Панель'

    @admin.action(description='Активировать выбранные игры и деактивировать остальные')
    def activate_selected_games(self, request, queryset):
        selected_ids = list(queryset.values_list('id', flat=True))
        models.Game.objects.exclude(id__in=selected_ids).update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, f'Активировано {queryset.count()} игра(ы), остальные деактивированы.')

    @admin.action(description='Дублировать выбранные игры (с раундами и вопросами)')
    def duplicate_games(self, request, queryset):
        created = 0
        with transaction.atomic():
            for game in queryset:
                new_game = models.Game.objects.create(
                    title=f"{game.title} (копия)",
                    description=game.description,
                    is_active=False,
                    mode=game.mode,
                )
                for rnd in game.rounds.all().order_by('order'):
                    new_round = models.Round.objects.create(
                        game=new_game,
                        title=rnd.title,
                        order=rnd.order,
                        description=rnd.description,
                    )
                    for q in rnd.questions.all():
                        models.Question.objects.create(
                            round=new_round,
                            text=q.text,
                            type=q.type,
                            options=q.options,
                            correct_answer=q.correct_answer,
                            points=q.points,
                            allow_bet=q.allow_bet,
                            bet_multiplier=q.bet_multiplier,
                        )
                created += 1
        self.message_user(request, f'Создано копий: {created}.')


@admin.register(models.Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'game', 'order')
    search_fields = ('title', 'description', 'game__title')


@admin.register(models.Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'round', 'type', 'points', 'allow_bet')
    search_fields = ('text',)


@admin.register(models.Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'user_id', 'team_name', 'is_correct', 'points_awarded', 'submitted_at')
    search_fields = ('user_id', 'team_name', 'answer_text')


@admin.register(models.Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_key', 'game', 'team_name', 'registered_at')
    search_fields = ('session_key', 'team_name')
