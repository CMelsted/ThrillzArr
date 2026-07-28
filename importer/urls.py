from django.urls import path, re_path
from . import views
urlpatterns = [
    path('', views.ImportView.as_view(), name='import'),
    path('match', views.MatchView.as_view(), name='match'),
    re_path(r'^asin-search/$', views.AsinSearch.as_view(), name='asin-search'),
    path('review', views.ReviewView.as_view(), name='review'),
    path('books', views.BookListView.as_view(), name='books'),
    path('books/clear', views.ClearJobsView.as_view(), name='clear-jobs'),
    path('book/<int:book_id>/edit', views.EditBookView.as_view(), name='edit-book'),
    path('book/<int:book_id>/status', views.BookStatusView.as_view(), name='book-status'),
    path('book/<int:book_id>/abandon', views.AbandonJobView.as_view(), name='abandon-job'),
    path('presets', views.PresetsView.as_view(), name='presets'),
    path('setting', views.SettingView.as_view(), name='setting'),
]
