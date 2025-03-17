import json
import time
import os
import random
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, Dict

# Configuração de logging para salvar os logs em um arquivo, com mensagens em português
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Carregar variáveis de ambiente
load_dotenv()

# Carregar o token do Discord e chave da API do Google
discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')

if not discord_token or not google_api_key:
    logging.error("Erro: Token do Discord ou chave da API do Google não encontrados.")
    exit(1)

# Configurações de reintento e tempos de espera
RETRY_LIMIT = 3
RETRY_DELAY = 5  # segundos entre tentativas
READ_DELAY = 5  # segundos entre leituras de mensagens
REPLY_DELAY = 3  # segundos entre respostas

last_message_id: Optional[str] = None
bot_user_id: Optional[str] = None
last_ai_response: Optional[str] = None  # Armazenar a última resposta da IA


banner = """
 ██████╗ ██╗  ██╗    ██████╗ ███████╗███╗   ██╗ █████╗ ███╗   ██╗
██╔═████╗╚██╗██╔╝    ██╔══██╗██╔════╝████╗  ██║██╔══██╗████╗  ██║
██║██╔██║ ╚███╔╝     ██████╔╝█████╗  ██╔██╗ ██║███████║██╔██╗ ██║
████╔╝██║ ██╔██╗     ██╔══██╗██╔══╝  ██║╚██╗██║██╔══██║██║╚██╗██║
╚██████╔╝██╔╝ ██╗    ██║  ██║███████╗██║ ╚████║██║  ██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""
print(banner)

# Função para logar mensagens no arquivo de log
def log_message(message: str) -> None:
    """Função para logar mensagens em português no arquivo de log"""
    logging.info(message)

def safe_request(func, *args, **kwargs):
    """Função auxiliar para fazer requisições de forma segura, com reintento em caso de falha"""
    for attempt in range(RETRY_LIMIT):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            log_message(f"⚠️ Erro na requisição ({attempt + 1}/{RETRY_LIMIT}): {e}. Tentando novamente...")
            time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Erro na requisição ({attempt + 1}/{RETRY_LIMIT}): {e}. Abortando após falha.")
            raise  # Aborta após o número máximo de tentativas
    log_message("⚠️ Erro na requisição, sem mais tentativas.")
    raise Exception("Falha ao realizar requisição após múltiplas tentativas.")

def generate_reply(user_message: str, language: str = "en") -> str:
    """Gera uma resposta curta e amigável usando a API do Google Gemini AI"""
    global last_ai_response

    ai_prompt = f"{user_message}\n\nRespond like a 25-year-old native English speaker, chill, sociable, and friendly. Keep the reply short, simple, and positive. Always try to help, like you're chatting with a friend."

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
    headers = {'Content-Type': 'application/json'}
    data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

    try:
        response = safe_request(requests.post, url, headers=headers, json=data)
        ai_response = response.json()

        response_text = ai_response['candidates'][0]['content']['parts'][0]['text']
        if not response_text.strip() or response_text == last_ai_response:
            log_message("⚠️ A resposta gerada é vazia ou igual à última. Tentando novamente.")
            return "Sorry, I can't think of anything right now, but I'm here to help!"
        
        last_ai_response = response_text.strip()
        return response_text.strip()

    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Erro ao gerar resposta da IA: {e}")
        return "Sorry, I couldn't get a good response. Can I help with anything else?"
    except Exception as e:
        log_message(f"⚠️ Erro ao processar a resposta: {e}")
        return "Something went wrong. Please try again later."

def send_message(channel_id: str, message_text: str, reply_to: Optional[str] = None) -> None:
    """Função para enviar mensagem ao Discord de forma simplificada"""
    payload = {'content': message_text}
    if reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    try:
        safe_request(requests.post, f"https://discord.com/api/v9/channels/{channel_id}/messages", 
                     json=payload, headers={'Authorization': discord_token, 'Content-Type': 'application/json'})
        log_message(f"✅ Mensagem enviada: {message_text}")
    except Exception as e:
        log_message(f"⚠️ Falha ao enviar mensagem: {e}")

def auto_reply(channel_id: str, read_delay: int = READ_DELAY, reply_delay: int = REPLY_DELAY) -> None:
    """Função para responder automaticamente às mensagens no Discord, com verificação de duplicação"""
    global last_message_id, bot_user_id

    headers = {'Authorization': discord_token}

    try:
        bot_info_response = safe_request(requests.get, 'https://discord.com/api/v9/users/@me', headers=headers)
        bot_user_id = bot_info_response.json().get('id')
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Falha ao obter informações do bot: {e}")
        return

    while True:
        try:
            response = safe_request(requests.get, f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)

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

                        response_text = generate_reply(user_message)

                        log_message(f"⏳ Esperando {reply_delay} segundos antes de responder...")
                        time.sleep(reply_delay)
                        send_message(channel_id, response_text, reply_to=message_id)
                        last_message_id = message_id

            log_message(f"⏳ Esperando {read_delay} segundos antes de verificar novas mensagens...")
            time.sleep(read_delay)

        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Erro na requisição: {e}")
            time.sleep(read_delay)

if __name__ == "__main__":
    use_reply = input("Do you want to use auto-reply? (y/n): ").lower() == 'y'
    channel_id = input("Enter the channel ID: ")

    if use_reply:
        read_delay = int(input("Set the read delay (in seconds): "))
        reply_delay = int(input("Set the reply delay (in seconds): "))

        log_message(f"✅ Auto-reply mode active... Waiting for messages in channel {channel_id}")
        auto_reply(channel_id, read_delay, reply_delay)
    else:
        log_message("❌ Auto-reply mode is off.")
