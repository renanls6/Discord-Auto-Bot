import json
import time
import os
import requests
import logging
from dotenv import load_dotenv
from typing import Optional
import random
from backoff import on_exception, expo
from requests.exceptions import RequestException

# Configuração de logging
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Carregar variáveis de ambiente
load_dotenv()

# Carregar o token do Discord, chave da API do Google e canais
discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')
channels = os.getenv('DISCORD_CHANNELS').split(',')

if not discord_token or not google_api_key or not channels:
    logging.error("Erro: Token do Discord, chave da API do Google ou canais não encontrados.")
    exit(1)

# Configurações de reintento e tempos de espera
RETRY_DELAY = 5  # segundos entre tentativas
READ_DELAY = int(os.getenv('READ_DELAY', 5))  # tempo entre leituras de mensagens
REPLY_DELAY = int(os.getenv('REPLY_DELAY', 3))  # tempo entre respostas

last_message_id: Optional[str] = None
bot_user_id: Optional[str] = None
last_ai_response: Optional[str] = None  # Armazenar a última resposta da IA

# Lista de gírias informais em inglês
slangs = [
    "yo", "dude", "bro", "what's up", "lit", "chill", "no worries", "bet", 
    "for real", "nah", "aight", "you know", "lol", "totally", "sick"
]

# Banner de boas-vindas
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
    """Função para logar mensagens no arquivo de log"""
    logging.info(message)

@on_exception(expo, RequestException, max_tries=5)
def safe_request(func, *args, **kwargs):
    """Função auxiliar para fazer requisições de forma segura, com backoff exponencial"""
    try:
        return func(*args, **kwargs)
    except RequestException as e:
        log_message(f"⚠️ Erro na requisição: {e}. Tentando novamente...")
        raise  # Repetir após erro

def generate_reply(user_message: str, language: str = "en") -> str:
    """Gera uma resposta curta e amigável usando a API do Google Gemini AI"""
    global last_ai_response

    ai_prompt = f"{user_message}\n\nRespond in a very casual, short, and natural way. Don't be formal, just keep it chill."

    # Adicionando gírias e uma abordagem mais informal em 30% das vezes
    if random.random() < 0.3:  # 30% chance de adicionar gírias
        ai_prompt += "\nUse slang like 'yo', 'dude', 'aight', 'nah', and keep it relaxed. No need for perfect grammar."

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
    headers = {'Content-Type': 'application/json'}
    data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

    try:
        response = safe_request(requests.post, url, headers=headers, json=data)
        ai_response = response.json()

        response_text = ai_response['candidates'][0]['content']['parts'][0]['text']
        if not response_text.strip() or response_text == last_ai_response:
            log_message("⚠️ A resposta gerada é vazia ou igual à última. Tentando novamente.")
            return "Yo, I can't think of anything right now, but I'm here if you need something."
        
        last_ai_response = response_text.strip()
        return response_text.strip()

    except RequestException as e:
        log_message(f"⚠️ Erro ao gerar resposta da IA: {e}")
        return "Sorry, I couldn't get a good reply, but I can help with something else."
    except Exception as e:
        log_message(f"⚠️ Erro ao processar a resposta: {e}")
        return "Something went wrong. Try again later."

def should_reply(user_message: str) -> bool:
    """Decide se o bot deve responder com base no conteúdo da mensagem"""
    if len(user_message.split()) < 3:  # Ignora mensagens curtas ou irrelevantes
        return False
    if '?' in user_message:  # Se for uma pergunta, sempre responde
        return True
    return random.random() < 0.7  # 70% chance de decidir responder

def send_message(channel_id: str, message_text: str, reply_to: Optional[str] = None) -> None:
    """Função para enviar mensagem ao Discord"""
    payload = {'content': message_text}
    if reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    try:
        safe_request(requests.post, f"https://discord.com/api/v9/channels/{channel_id}/messages", 
                     json=payload, headers={'Authorization': discord_token, 'Content-Type': 'application/json'})
        log_message(f"✅ Mensagem enviada: {message_text}")
        print(f"✅ Mensagem enviada: {message_text}")  # Exibe no console a resposta enviada
    except Exception as e:
        log_message(f"⚠️ Falha ao enviar mensagem: {e}")

def auto_reply(channels: list, read_delay: int = READ_DELAY, reply_delay: int = REPLY_DELAY) -> None:
    """Função para responder automaticamente às mensagens nos canais do Discord"""
    global last_message_id, bot_user_id

    headers = {'Authorization': discord_token}

    try:
        bot_info_response = safe_request(requests.get, 'https://discord.com/api/v9/users/@me', headers=headers)
        bot_user_id = bot_info_response.json().get('id')
    except RequestException as e:
        log_message(f"⚠️ Falha ao obter informações do bot: {e}")
        return

    while True:
        for channel_id in channels:
            print(f"⏳ Lendo novas mensagens no canal {channel_id}...")

            try:
                response = safe_request(requests.get, f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
                messages = response.json()

                if messages:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')

                    if (last_message_id is None or int(message_id) > int(last_message_id)) and author_id != bot_user_id and message_type != 8:
                        user_message = most_recent_message.get('content', '')
                        print(f"💬 Mensagem recebida: {user_message}")  # Exibe no console a mensagem recebida
                        log_message(f"💬 Mensagem recebida: {user_message}")

                        if should_reply(user_message):
                            response_text = generate_reply(user_message)
                        else:
                            response_text = "Nah, I'm just chillin' right now. Lemme know if you need something."

                        print(f"⏳ Respondendo: {response_text}")  # Exibe no console a resposta gerada
                        log_message(f"⏳ Respondendo: {response_text}")

                        time.sleep(reply_delay)
                        send_message(channel_id, response_text, reply_to=message_id)

                        last_message_id = message_id  # Atualiza o ID da última mensagem
            except RequestException as e:
                log_message(f"⚠️ Erro ao obter mensagens: {e}")

            time.sleep(read_delay)  # Aguarda um tempo antes de verificar novas mensagens

if __name__ == '__main__':
    auto_reply(channels)
