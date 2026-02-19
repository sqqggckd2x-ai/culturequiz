from django.urls import path
from . import views
from admin_panel import views as admin_views

app_name = 'quiz'

urlpatterns = [
    path('', views.index, name='index'),
    path('stream/<int:game_id>/', views.game_stream, name='game_stream'),
    path('game/<int:game_id>/register/', views.register_for_game, name='register_for_game'),
    path('game/<int:game_id>/play/', views.play_game, name='play_game'),
    path('game/<int:game_id>/ratings/', views.ratings, name='game_ratings'),
    path('game/<int:game_id>/ratings/public/', admin_views.public_participants_rating, name='public_game_ratings'),
]
