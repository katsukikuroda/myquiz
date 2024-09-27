from django.db import models

class UserQuizStatus(models.Model):
    user_id = models.CharField(max_length=255, unique=True)
    current_question_index = models.IntegerField(default=0)
    current_quiz_data = models.JSONField(default=list)  # クイズデータを保存するためのフィールド

    def __str__(self):
        return self.user_id
