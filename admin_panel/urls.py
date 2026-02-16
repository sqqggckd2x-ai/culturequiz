from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('<int:game_id>/manage/', views.manage_game, name='manage_game'),
    path('<int:game_id>/send_question/<int:question_id>/', views.send_question, name='send_question'),
    path('<int:game_id>/stop_answers/', views.stop_answers, name='stop_answers'),
    path('<int:game_id>/moderate/', views.moderate_answers, name='moderate_answers'),
    path('<int:game_id>/mark_answer/<int:answer_id>/', views.mark_answer, name='mark_answer'),
]
