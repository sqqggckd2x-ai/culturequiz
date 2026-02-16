from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # admin-panel custom views for game management
    path('admin/game/', include('admin_panel.urls')),
    path('admin/', admin.site.urls),
    path('', include('quiz.urls')),
]
