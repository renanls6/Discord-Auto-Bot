

import json
import time
import shareithub
import os
import random
import requests
from dotenv import load_dotenv
from datetime import datetime
from shareithub import shareithub

# Inicializando o Shareithub e carregando as variáveis de ambiente
shareithub()
load_dotenv()

# Carregar o token do Discord
discord_token = os.getenv('DISCORD_TOKEN')
if not discord_token:
    print("Erro: O token do Discord não foi encontrado ou está incorreto.")
    exit(1)  # Finalizar o script, pois o token é essencial para a autenticação

# Carregar a chave da API do Google
google_api_key = os.getenv('GOOGLE_API_KEY')
if not google_api_key:
    print("Erro: A chave da API do Google não foi encontrada ou está incorreta.")
    exit(1)  # Finalizar o script, pois a chave da API do Google é essencial para a comunicação com o Google AI

last_message_id = None
bot_user_id = None
last_ai_response = None  # Armazenar a última resposta da IA

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def generate_reply(prompt, use_google_ai=True, use_file_reply=False, language="id"):
    """Gera uma resposta, evitando duplicação ao usar o Google Gemini AI"""

    global last_ai_response  # Usar a variável global para ser acessada em toda a sessão

    if use_file_reply:
        log_message("💬 Usando mensagem do arquivo como resposta.")
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

    if use_google_ai:
        # Escolha de idioma
        if language == "en":
            ai_prompt = f"{prompt}\n\nResponda de forma descontraída, jovem e simpática, como se fosse uma conversa de amigo. Não use símbolos ou palavras complicadas, só fale de forma natural, como alguém que ama bater papo e está sempre disposto a ajudar."
        else:
            ai_prompt = f"{prompt}\n\nResponda de forma descontraída, jovem e simpática, como se fosse uma conversa de amigo. Não use símbolos ou palavras complicadas, só fale de forma natural, como alguém que ama bater papo e está sempre disposto a ajudar."

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

        for attempt in range(3):  # Tentar até 3 vezes se a IA repetir a mesma mensagem
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                ai_response = response.json()

                # Obter o texto da resposta da IA
                response_text = ai_response['candidates'][0]['content']['parts'][0]['text']

                # Verificar se a resposta da IA é a mesma que a última
                if response_text == last_ai_response:
                    log_message("⚠️ IA deu a mesma resposta, tentando novamente...")
                    continue  # Tentar novamente com uma nova solicitação
                
                last_ai_response = response_text  # Salvar a última resposta
                return ai_response

            except requests.exceptions.RequestException as e:
                log_message(f"⚠️ Falha na requisição: {e}")
                return None

        log_message("⚠️ A IA continua dando a mesma resposta, usando a última resposta disponível.")
        return {"candidates": [{"content": {"parts": [{"text": last_ai_response or 'Desculpe, não posso responder agora, mas tô aqui pra ajudar!'}]}}]}

    else:
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

def get_random_message():
    """Obter uma mensagem aleatória do arquivo de mensagens"""
    try:
        with open('pesan.txt', 'r') as file:
            lines = file.readlines()
            if lines:
                return random.choice(lines).strip()
            else:
                log_message("O arquivo 'pesan.txt' está vazio.")
                return "Não há mensagens disponíveis."
    except FileNotFoundError:
        log_message("Arquivo 'pesan.txt' não encontrado.")
        return "Arquivo 'pesan.txt' não encontrado."

def send_message(channel_id, message_text, reply_to=None, reply_mode=True):
    """Enviar mensagem para o Discord, pode ser com ou sem resposta"""
    headers = {
        'Authorization': f'{discord_token}',
        'Content-Type': 'application/json'
    }

    payload = {'content': message_text}

    # Somente adicionar resposta se o modo de resposta estiver ativado
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
        log_message(f"⚠️ Erro na requisição: {e}")

def auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language, reply_mode):
    """Função para resposta automática no Discord, evitando duplicação de respostas da IA"""
    global last_message_id, bot_user_id

    headers = {'Authorization': f'{discord_token}'}

    try:
        bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
        bot_info_response.raise_for_status()
        bot_user_id = bot_info_response.json().get('id')
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Falha ao obter informações do bot: {e}")
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
                        response_text = result['candidates'][0]['content']['parts'][0]['text'] if result else "Desculpe, não posso responder."

                        log_message(f"⏳ Esperando {reply_delay} segundos antes de responder...")
                        time.sleep(reply_delay)
                        send_message(channel_id, response_text, reply_to=message_id if reply_mode else None, reply_mode=reply_mode)
                        last_message_id = message_id

            log_message(f"⏳ Esperando {read_delay} segundos antes de verificar novas mensagens...")
            time.sleep(read_delay)
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Erro na requisição: {e}")
            time.sleep(read_delay)

if __name__ == "__main__":
    use_reply = input("Deseja usar a funcionalidade de resposta automática? (y/n): ").lower() == 'y'
    channel_id = input("Digite o ID do canal: ")

    if use_reply:
        use_google_ai = input("Usar o Google Gemini AI para respostas? (y/n): ").lower() == 'y'
        use_file_reply = input("Usar mensagens do arquivo 'pesan.txt'? (y/n): ").lower() == 'y'
        reply_mode = input("Deseja responder às mensagens (reply) ou enviar apenas uma mensagem? (reply/send): ").lower() == 'reply'
        language_choice = input("Escolha o idioma para a resposta (id/en): ").lower()

        if language_choice not in ["id", "en"]:
            log_message("⚠️ Idioma inválido, usando o idioma indonésio por padrão.")
            language_choice = "id"

        read_delay = int(input("Defina o intervalo para ler mensagens novas (em segundos): "))
        reply_delay = int(input("Defina o intervalo para responder às mensagens (em segundos): "))

        log_message(f"✅ Modo de resposta {'ativo' if reply_mode else 'não-reply'} em {'Indonésio' if language_choice == 'id' else 'Inglês'}...")
        auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language_choice, reply_mode)

    else:
        send_interval = int(input("Defina o intervalo para enviar mensagens (em segundos): "))
        log_message("✅ Modo de envio de mensagens aleatórias ativo...")

        while True:
            message_text = get_random_message()
            send_message(channel_id, message_text, reply_mode=False)
            log_message(f"⏳ Esperando {send_interval} segundos antes de enviar a próxima mensagem...")
            time.sleep(send_interval)



