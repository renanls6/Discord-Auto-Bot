import json
import time
import random
import requests
from dotenv import load_dotenv
from datetime import datetime
from shareithub import shareithub

shareithub()
load_dotenv()

discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')

last_message_id = None
bot_user_id = None
last_ai_response = None  # Menyimpan respons AI terakhir

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def generate_reply(prompt, use_google_ai=True, use_file_reply=False, language="id"):
    """Membuat balasan dengan gaya muda, ramah, dan optimis tanpa emoji."""

    global last_ai_response  # Gunakan variabel global agar dapat diakses di seluruh sesi

    if use_file_reply:
        log_message("💬 Menggunakan pesan dari file sebagai balasan.")
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

    if use_google_ai:
        # Pilihan bahasa com tom otimista, mas sem emojis
        if language == "en":
            ai_prompt = f"{prompt}\n\nRespond with a short, positive, and friendly sentence. Be enthusiastic and eager to help, like a young person excited to contribute to the community. Avoid getting involved in any argument, and keep the tone uplifting and helpful."
        else:
            ai_prompt = f"{prompt}\n\nBalas dengan satu kalimat yang ceria, ramah, dan penuh semangat tanpa menggunakan emoji. Seperti seseorang muda yang senang membantu dan tidak terlibat dalam perdebatan. Ciptakan suasana yang positif dan ingin membantu semua orang."

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

        for attempt in range(3):  # Coba sampai 3 kali jika AI mengulang pesan yang sama
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                ai_response = response.json()

                # Ambil teks dari respons AI
                response_text = ai_response['candidates'][0]['content']['parts'][0]['text']

                # Cek apakah respons AI sama dengan yang terakhir
                if response_text == last_ai_response:
                    log_message("⚠️ AI memberikan balasan yang sama, mencoba ulang...")
                    continue  # Coba lagi dengan permintaan baru
                
                last_ai_response = response_text  # Simpan respons terbaru
                return ai_response

            except requests.exceptions.RequestException as e:
                log_message(f"⚠️ Request failed: {e}")
                return None

        log_message("⚠️ AI terus memberikan balasan yang sama, menggunakan respons terakhir yang tersedia.")
        return {"candidates": [{"content": {"parts": [{"text": last_ai_response or 'Desculpe, não consegui te ajudar agora. Vou tentar novamente em breve.'}]}}]}

    else:
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

def get_random_message():
    """Mengambil pesan acak dari file pesan.txt"""
    try:
        with open('pesan.txt', 'r') as file:
            lines = file.readlines()
            if lines:
                return random.choice(lines).strip()
            else:
                log_message("File pesan.txt kosong.")
                return "Não há mensagens disponíveis no momento."
    except FileNotFoundError:
        log_message("File pesan.txt não encontrado.")
        return "Arquivo de mensagens não encontrado."

def send_message(channel_id, message_text, reply_to=None, reply_mode=True):
    """Enviar mensagem para o Discord sem emojis"""
    headers = {
        'Authorization': f'{discord_token}',
        'Content-Type': 'application/json'
    }

    payload = {'content': message_text}

    # Só adiciona a resposta se o reply_mode estiver ativado
    if reply_mode and reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    try:
        response = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", json=payload, headers=headers)
        response.raise_for_status()

        if response.status_code == 201:
            log_message(f"✅ Mensagem enviada: {message_text}")
        else:
            log_message(f"⚠️ Falha ao enviar mensagem: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Erro de requisição: {e}")

def auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language, reply_mode):
    """Função para auto-resposta no Discord com estilo otimista e acolhedor sem emojis"""
    global last_message_id, bot_user_id

    headers = {'Authorization': f'{discord_token}'}

    try:
        bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
        bot_info_response.raise_for_status()
        bot_user_id = bot_info_response.json().get('id')
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Falha ao recuperar informações do bot: {e}")
        return

    while True:
        try:
            response = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                messages = response.json()
                if len(messages) > 0:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')

                    if (last_message_id is None or int(message_id) > int(last_message_id)) and author_id != bot_user_id and message_type != 8:
                        user_message = most_recent_message.get('content', '')
                        log_message(f"💬 Mensagem recebida: {user_message}")

                        result = generate_reply(user_message, use_google_ai, use_file_reply, language)
                        response_text = result['candidates'][0]['content']['parts'][0]['text'] if result else "Desculpe, não consegui processar sua mensagem."

                        log_message(f"⏳ Aguardando {reply_delay} segundos antes de responder...")
                        time.sleep(reply_delay)
                        send_message(channel_id, response_text, reply_to=message_id if reply_mode else None, reply_mode=reply_mode)
                        last_message_id = message_id

            log_message(f"⏳ Aguardando {read_delay} segundos antes de verificar novas mensagens...")
            time.sleep(read_delay)
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Erro de requisição: {e}")
            time.sleep(read_delay)

if __name__ == "__main__":
    use_reply = input("Deseja usar a função de auto-resposta? (y/n): ").lower() == 'y'
    channel_id = input("Digite o ID do canal: ")

    if use_reply:
        use_google_ai = input("Usar Google Gemini AI para as respostas? (y/n): ").lower() == 'y'
        use_file_reply = input("Usar mensagens do arquivo mensagem.txt? (y/n): ").lower() == 'y'
        reply_mode = input("Responder às mensagens ou apenas enviar uma nova? (reply/send): ").lower() == 'reply'
        language_choice = input("Escolha o idioma para as respostas (pt/en): ").lower()

        if language_choice not in ["pt", "en"]:
            log_message("⚠️ Idioma não válido, padrão para português.")
            language_choice = "pt"

        read_delay = int(input("Defina o intervalo de leitura de mensagens (em segundos): "))
        reply_delay = int(input("Defina o intervalo para responder às mensagens (em segundos): "))

        log_message(f"✅ Modo de resposta {'ativo' if reply_mode else 'desativado'} no idioma {'português' if language_choice == 'pt' else 'inglês'}...")
        auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language_choice, reply_mode)

    else:
        send_interval = int(input("Defina o intervalo de envio de mensagens (em segundos): "))
        log_message("✅ Modo de envio de mensagens aleatórias ativo...")

        while True:
            message_text = get_random_message()
            send_message(channel_id, message_text, reply_mode=False)
            log_message(f"⏳ Aguardando {send_interval} segundos antes de enviar a próxima mensagem...")
            time.sleep(send_interval)
