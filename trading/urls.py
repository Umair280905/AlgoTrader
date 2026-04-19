from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('trades/', views.trades, name='trades'),
    path('reports/', views.reports, name='reports'),
    path('journal/', views.journal, name='journal'),
    path('settings/', views.settings_view, name='settings'),
    # REST API
    path('api/positions/', views.api_positions, name='api_positions'),
    path('api/pnl/', views.api_pnl, name='api_pnl'),
    path('api/signals/', views.api_signals, name='api_signals'),
    path('ai/chat/', views.ai_chat, name='ai_chat'),
    path('ai/chat/send/', views.ai_chat_send, name='ai_chat_send'),
    path('api/ai/scores/', views.api_ai_scores, name='api_ai_scores'),
    path('api/ai/suggestions/', views.api_tuner_suggestions, name='api_tuner_suggestions'),
]
