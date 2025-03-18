import random
import time
import os
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional
import re
from backoff import on_exception, expo

# Configuração de logging
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
print("🔗 Curtiu o Bot? Me siga lá no  Twitter: https://x.com/0x_renan")

# Função para logar mensagens no arquivo de log
def log_message(message: str) -> None:
    """Função para logar mensagens em português no arquivo de log"""
    logging.info(message)

@on_exception(expo, requests.exceptions.RequestException, max_tries=5)
def safe_request(func, *args, **kwargs):
    """Função auxiliar para fazer requisições de forma segura, com backoff exponencial"""
    try:
        return func(*args, **kwargs)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        log_message(f"⚠️ Erro na requisição: {e}. Tentando novamente...")
        raise
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Erro na requisição: {e}. Abortando após falha.")
        raise  # Aborta após falha

def generate_reply(user_message: str) -> str:
    """Gera uma resposta descontraída e informal do bot com base no conteúdo da mensagem"""
    # Normaliza a mensagem (remover espaços extras e transformar em minúsculas)
    normalized_message = user_message.strip().lower()

    # Respostas para diferentes situações
    if re.search(r'\b(need|help|assist)\b', normalized_message):
        # Respostas quando o usuário está pedindo ajuda
        response_text = random.choice([
            "Ayy, I gotchu! What do you need help with?",
            "Yo, you need something? I'm here to help.",
            "I'm here for ya, what do you need help with?",
            "Lemme know what you need, I'm all ears."
        ])
    
    elif re.search(r'\b(sad|down|feeling)\b', normalized_message):
        # Respostas quando o usuário parece estar triste ou chateado
        response_text = random.choice([
            "Yo, I feel you. Sometimes we all need a little space.",
            "Ayy, it's all good, we all have those days. You good?",
            "I get it, sometimes things feel off, but hang in there.",
            "It’s okay to feel down sometimes, but you’re not alone."
        ])
    
    elif re.search(r'\b(happy|good|great)\b', normalized_message):
        # Respostas quando o usuário está feliz ou empolgado
        response_text = random.choice([
            "Ayy, that's awesome! Keep that energy going!",
            "Yo, love that vibe! Keep shining!",
            "Woooo, that's what I like to hear! Let's keep that good energy up!",
            "That's great! Keep riding that high, you deserve it."
        ])
    
    else:
        # Se a mensagem não for relevante (não contém as palavras-chave), o bot não responde.
        response_text = None

    return response_text

def should_reply(user_message: str) -> bool:
    """Decide se o bot deve responder com base no conteúdo da mensagem"""
    # O bot agora responde 60% das vezes
    return random.random() < 0.60  # 60% de chance de responder

def send_message(channel_id: str, message_text: str, reply_to: Optional[str] = None) -> None:
    """Função para enviar mensagem ao Discord de forma simplificada"""
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
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Falha ao obter informações do bot: {e}")
        return

    while True:
        for channel_id in channels:
            print(f"⏳ Lendo novas mensagens no canal {channel_id}...")

            response = safe_request(requests.get, f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)

            if response.status_code == 200:
                messages = response.json()
                if len(messages) > 0:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')

                    # Apenas responder a mensagens que não são do bot
                    if (last_message_id is None or int(message_id) > int(last_message_id)) and author_id != bot_user_id and message_type != 8:
                        user_message = most_recent_message.get('content', '')
                        print(f"💬 Mensagem recebida: {user_message}")  # Exibe no console a mensagem recebida
                        log_message(f"💬 Mensagem recebida: {user_message}")

                        # Decisão de responder ou não
                        if should_reply(user_message):
                            response_text = generate_reply(user_message)
                        else:
                            response_text = None  # Não responde, apenas observa

                        if response_text:
                            print(f"⏳ Respondendo: {response_text}")  # Exibe no console a resposta gerada
                            log_message(f"⏳ Respondendo: {response_text}")
                            time.sleep(reply_delay)
                            send_message(channel_id, response_text, reply_to=message_id)
                        
                        last_message_id = message_id  # Atualiza o ID da última mensagem

            time.sleep(read_delay)  # Aguarda um tempo antes de verificar novas mensagens

def main():
    channels = [
        os.getenv("DISCORD_CHANNEL_1"),
        os.getenv("DISCORD_CHANNEL_2"),
        os.getenv("DISCORD_CHANNEL_3"),
        os.getenv("DISCORD_CHANNEL_4"),
        os.getenv("DISCORD_CHANNEL_5"),
    ]

    # Inicia a função de resposta automática
    auto_reply(channels)

if __name__ == '__main__':
    main()
