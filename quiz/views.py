import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from .models import UserQuizStatus
import random
import time

# LINE Bot API
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

# Google Sheetsのデータを取得する関数
def get_quiz_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials/myquiz-436811-bc8b0951f8bd.json', scope)
    client = gspread.authorize(creds)
    spreadsheet_id = '1vAwXuWs_YVCEPdwMjkrAPq7dTuq1TWdscm75LZyiPdw'
    sheet = client.open_by_key(spreadsheet_id)
    worksheet = sheet.worksheet('シート1')
    data = worksheet.get_all_records()  # 1行目をスキップしてデータを取得
    return data

# Webhookを処理する関数
@csrf_exempt
def webhook(request):
    if request.method == 'POST':
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')

        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            return HttpResponse(status=400)

        return HttpResponse(status=200)
    else:
        return HttpResponse(status=405)


# メッセージイベントに応答する関数
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    message_text = event.message.text.strip()

    # ユーザーの状態をデータベースから取得または作成
    user_status, created = UserQuizStatus.objects.get_or_create(user_id=user_id)

    # 「終了」と入力された場合は初期状態にリセット
    if message_text == "終了":
        user_status.current_question_index = 0
        user_status.current_quiz_data = []
        user_status.save()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="終了しました。"))
        return

    # スタートの場合、問題をランダムに並び替えて表示開始
    if message_text == "スタート":
        quiz_data = get_quiz_data()  # クイズデータを取得
        random.shuffle(quiz_data)  # ランダムに並び替え
        user_status.current_quiz_data = quiz_data
        user_status.current_question_index = 0
        user_status.save()

        # 最初の問題を表示
        first_question = quiz_data[0]
        question_text = f"問題: {first_question['問題']}\n1. {first_question['選択肢1']}\n2. {first_question['選択肢2']}\n3. {first_question['選択肢3']}\n4. {first_question['選択肢4']}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=question_text))
        return

    # クイズが進行中の場合の処理
    if user_status.current_quiz_data:
        current_index = user_status.current_question_index
        quiz_data = user_status.current_quiz_data

        # 数字（1〜4）を送信された場合の正解判定
        if message_text in ['1', '2', '3', '4']:
            user_answer = int(message_text)
            correct_answer = int(quiz_data[current_index]['解答'])

            if user_answer == correct_answer:
                result_text = "正解！"
            else:
                result_text = f"残念…正解は{correct_answer}番です。"

            # 結果を表示
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result_text))

            # 次の問題があれば1秒後に表示
            user_status.current_question_index += 1
            if user_status.current_question_index < len(quiz_data):
                next_question = quiz_data[user_status.current_question_index]
                time.sleep(1)  # 1秒待機して次の問題を表示
                question_text = f"問題: {next_question['問題']}\n1. {next_question['選択肢1']}\n2. {next_question['選択肢2']}\n3. {next_question['選択肢3']}\n4. {next_question['選択肢4']}"
                line_bot_api.push_message(user_id, TextSendMessage(text=question_text))
            else:
                # すべての問題が終わったら終了メッセージ
                line_bot_api.push_message(user_id, TextSendMessage(text="終了しました"))
                user_status.current_question_index = 0
                user_status.current_quiz_data = []
            user_status.save()
        else:
            # 1〜4以外のテキストが送られた場合は何もしない
            pass
    else:
        # クイズが開始されていない場合
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="「スタート」と入力してください！"))
