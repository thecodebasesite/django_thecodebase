
import logging
import re
import requests
import github
import markdown
import celery

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import Topic, Repo, GithubToken
from .models import Game, Score, JavaScriptFile


_logger = logging.getLogger(__name__)


@celery.shared_task
def fetch_repos_task(token):

    def prettify(repo_name):
        words = re.split(r'[ \-_]', repo_name)
        words = [word.capitalize() for word in words]
        return ' '.join(words)

    def update_or_create(Model, vals, **search_kwargs):
        objects = getattr(Model, 'objects')
        record, created = objects.get_or_create(**search_kwargs, defaults=vals)
        if not created:
            for attr, value in vals.items():
                setattr(record, attr, value)
            record.save()
        return record

    ghub = github.Github(token)
    for repo in ghub.get_user().get_repos():
        if not repo.private:
            try:
                readme = repo.get_readme()
            except:
                continue

            _logger.info("Saving repo %s", repo.name)
            vals = {
                'name': repo.name,
                'display_name': prettify(repo.name),
                'readme_html': markdown.markdown(
                    requests.get(readme.download_url).text),
            }
            repo_record = update_or_create(Repo, vals, name=repo.name)

            topics = repo.get_topics()

            for topic_name in topics:
                vals = Topic.default_get(topic_name)
                topic_record = update_or_create(Topic, vals, url=topic_name)
                topic_record.repos.add(repo_record)
                topic_record.save()




class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'sequence')

admin.site.register(Game, GameAdmin)



class ScoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'time', 'score')

admin.site.register(Score, ScoreAdmin)



class JavaScriptFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'path', 'game', 'sequence')


admin.site.register(JavaScriptFile, JavaScriptFileAdmin)



class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'sequence')


admin.site.register(Topic, TopicAdmin)



class GithubTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sequence')
    actions = ['fetch_repos']

    def fetch_repos(self, request, queryset):
        for token_obj in queryset:
            fetch_repos_task.delay(token_obj.token)

        messages.add_message(request, messages.INFO, "%s github tokens will be processed asyncronosly" % len(queryset))

        return HttpResponseRedirect('/')


    fetch_repos.short_description = "Fetch Repositories"


admin.site.register(GithubToken, GithubTokenAdmin)


class RepoAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sequence', 'update_date')


admin.site.register(Repo, RepoAdmin)


