import json
import time
import random
import requests
from dotenv import load_dotenv
from datetime import datetime
from shareithub import shareithub
import os  # Importando 'os' corretamente

# Carregar variáveis de ambiente
load_dotenv()

discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')

# Inicializando o Shareithub e imprimindo o banner
shareithub()

banner = """
 ██████╗ ██╗  ██╗    ██████╗ ███████╗███╗   ██╗ █████╗ ███╗   ██╗
██╔═████╗╚██╗██╔╝    ██╔══██╗██╔════╝████╗  ██║██╔══██╗████╗  ██║
██║██╔██║ ╚███╔╝     ██████╔╝█████╗  ██╔██╗ ██║███████║██╔██╗ ██║
████╔╝██║ ██╔██╗     ██╔══██╗██╔══╝  ██║╚██╗██║██╔══██║██║╚██╗██║
╚██████╔╝██╔╝ ██╗    ██║  ██║███████╗██║ ╚████║██║  ██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""
print(banner)

def log_message(message):
    """Logar mensagens com timestamp"""
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {message}")

def request_with_retry(url, method='GET', data=None, retries=3, headers=None):
    """Função para realizar requisições HTTP com tentativas de reenvio em caso de falhas"""
    for attempt in range(retries):
        try:
            response = requests.request(method, url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Tentativa {attempt + 1} falhou: {e}")
            if attempt == retries - 1:
                log_message(f"⚠️ Falha ao fazer requisição após {retries} tentativas.")
                return None
            time.sleep(2)

def generate_reply(prompt, use_google_ai=True, use_file_reply=False, language="id"):
    """Gerar resposta de IA com um estilo jovem, positivo e otimista"""
    global last_ai_response

    if use_file_reply:
        log_message("💬 Usando mensagem de arquivo como resposta.")
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

    ai_prompt = f"{prompt}\n\n"
    if use_google_ai:
        ai_prompt += ("Respond with a short, positive, and friendly sentence. Be enthusiastic and eager to help, "
                      "like a young person excited to contribute to the community. Avoid getting involved in any argument.")
    else:
        ai_prompt += "Balas con una actitud positiva y amigable."

    # API request setup
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
    headers = {'Content-Type': 'application/json'}
    data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

    response_data = request_with_retry(url, 'POST', data, retries=3, headers=headers)

    if response_data:
        response_text = response_data['candidates'][0]['content']['parts'][0]['text']
        if response_text == last_ai_response:
            log_message("⚠️ A IA está repetindo a mesma resposta, tentando novamente.")
            return generate_reply(prompt, use_google_ai, use_file_reply, language)  # Recurssão para tentar novamente
        last_ai_response = response_text
        return response_data
    return {"candidates": [{"content": {"parts": [{"text": 'Desculpe, não consegui te ajudar agora.'}]}}]}

def get_random_message():
    """Obter mensagem aleatória do arquivo 'pesan.txt'"""
    try:
        with open('pesan.txt', 'r') as file:
            lines = file.readlines()
            return random.choice(lines).strip() if lines else "Não há mensagens disponíveis no momento."
    except FileNotFoundError:
        log_message("⚠️ Arquivo 'pesan.txt' não encontrado.")
        return "Arquivo de mensagens não encontrado."

def send_message(channel_id, message_text, reply_to=None, reply_mode=True):
    """Enviar uma mensagem no Discord"""
    headers = {
        'Authorization': f'Bearer {discord_token}',
        'Content-Type': 'application/json'
    }

    payload = {'content': message_text}
    if reply_mode and reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    response_data = request_with_retry(f"https://discord.com/api/v9/channels/{channel_id}/messages", 'POST', payload, headers=headers)

    if response_data:
        log_message(f"✅ Mensagem enviada: {message_text}")
    else:
        log_message(f"⚠️ Falha ao enviar mensagem.")

def auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language, reply_mode):
    """Função para auto-resposta no Discord com estilo otimista e acolhedor"""
    global last_message_id, bot_user_id

    headers = {'Authorization': f'Bearer {discord_token}'}

    # Obter informações do bot
    bot_info_response = request_with_retry('https://discord.com/api/v9/users/@me', 'GET', headers=headers)
    if bot_info_response:
        bot_user_id = bot_info_response.get('id')

    while True:
        # Ler mensagens do canal
        response = request_with_retry(f'https://discord.com/api/v9/channels/{channel_id}/messages', 'GET', headers=headers)
        if response:
            messages = response
            if messages:
                most_recent_message = messages[0]
                message_id = most_recent_message.get('id')
                author_id = most_recent_message.get('author', {}).get('id')

                if (last_message_id is None or int(message_id) > int(last_message_id)) and author_id != bot_user_id:
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
