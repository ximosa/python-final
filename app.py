import streamlit as st
import os
import json
import logging
import time
import requests
import tempfile
import random
from google.cloud import texttospeech
from moviepy.editor import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from io import BytesIO
import nltk
from nltk.corpus import stopwords

# Descargar recursos para procesamiento de texto
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
    nltk.download('punkt')

logging.basicConfig(level=logging.INFO)

# Cargar credenciales de GCP desde secrets
credentials = dict(st.secrets.gcp_service_account)
with open("google_credentials.json", "w") as f:
    json.dump(credentials, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

# Configuración de voces
VOCES_DISPONIBLES = {
    'es-ES-Standard-A': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Standard-B': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Standard-C': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Standard-D': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Standard-E': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Standard-F': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Neural2-A': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Neural2-B': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Neural2-C': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Neural2-D': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Neural2-E': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Neural2-F': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Polyglot-1': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Studio-C': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Studio-F': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Wavenet-B': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Wavenet-C': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Wavenet-D': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Wavenet-E': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Wavenet-F': texttospeech.SsmlVoiceGender.FEMALE,
}

# Mapeo de categorías a videos de stock (deberías tener estos videos en tu servidor)
# Si no tienes videos, puedes descargarlos de Pexels, Pixabay, etc. (gratuitos)
VIDEO_CATEGORIES = {
    "naturaleza": ["videos/stock/nature1.mp4", "videos/stock/nature2.mp4", "videos/stock/nature3.mp4"],
    "tecnología": ["videos/stock/tech1.mp4", "videos/stock/tech2.mp4"],
    "negocios": ["videos/stock/business1.mp4", "videos/stock/business2.mp4"],
    "educación": ["videos/stock/education1.mp4", "videos/stock/education2.mp4"],
    "ciencia": ["videos/stock/science1.mp4", "videos/stock/science2.mp4"],
    "deportes": ["videos/stock/sports1.mp4", "videos/stock/sports2.mp4"],
    "comida": ["videos/stock/food1.mp4", "videos/stock/food2.mp4"],
    "viajes": ["videos/stock/travel1.mp4", "videos/stock/travel2.mp4"],
    "abstracto": ["videos/stock/abstract1.mp4", "videos/stock/abstract2.mp4"],
    "default": ["videos/stock/default1.mp4", "videos/stock/default2.mp4"]
}

# Configuración de palabras clave para categorías
CATEGORY_KEYWORDS = {
    "naturaleza": ["naturaleza", "bosque", "montaña", "río", "lago", "mar", "océano", "animal", "planta", "flor"],
    "tecnología": ["tecnología", "computadora", "digital", "internet", "móvil", "app", "código", "robot", "ai", "ia"],
    "negocios": ["negocio", "empresa", "dinero", "finanzas", "marketing", "venta", "trabajo", "oficina", "emprendedor"],
    "educación": ["educación", "escuela", "aprendizaje", "estudio", "universidad", "conocimiento", "libro", "enseñanza"],
    "ciencia": ["ciencia", "científico", "investigación", "laboratorio", "experimento", "física", "química", "biología"],
    "deportes": ["deporte", "fútbol", "baloncesto", "tenis", "atleta", "juego", "competición", "ejercicio", "gimnasio"],
    "comida": ["comida", "alimento", "cocina", "receta", "restaurante", "chef", "plato", "bebida", "pastel", "postre"],
    "viajes": ["viaje", "turismo", "vacaciones", "hotel", "playa", "aventura", "explorar", "destino", "cultura"],
    "abstracto": ["concepto", "idea", "pensamiento", "filosofía", "abstracto", "mental", "teoría", "imaginación"]
}

# Función para detectar categoría de texto
def detect_category(text):
    text = text.lower()
    # Eliminar palabras comunes y tokenizar
    stop_words = set(stopwords.words('spanish'))
    words = [word for word in nltk.word_tokenize(text) if word.isalpha() and word not in stop_words]
    
    # Contar coincidencias por categoría
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for word in words if any(keyword in word for keyword in keywords))
        category_scores[category] = score
    
    # Elegir la categoría con más coincidencias o "default" si no hay coincidencias
    if max(category_scores.values(), default=0) > 0:
        return max(category_scores.items(), key=lambda x: x[1])[0]
    return "default"

# Función para seleccionar un video de stock basado en el texto
def select_stock_video(text, duration=5):
    try:
        category = detect_category(text)
        if category in VIDEO_CATEGORIES and VIDEO_CATEGORIES[category]:
            # Seleccionar aleatoriamente un video de la categoría
            video_path = random.choice(VIDEO_CATEGORIES[category])
            if os.path.exists(video_path):
                return video_path
        
        # Si no se encuentra un video específico, usar uno por defecto
        if VIDEO_CATEGORIES["default"] and os.path.exists(VIDEO_CATEGORIES["default"][0]):
            return VIDEO_CATEGORIES["default"][0]
    except Exception as e:
        logging.error(f"Error al seleccionar video: {str(e)}")
    
    return None  # Si no hay videos disponibles

# Función para crear un video abstracto básico como fallback
def create_basic_background(duration=5, output_path="temp_basic_bg.mp4"):
    try:
        # Crear una secuencia de frames con colores cambiantes
        frames = []
        fps = 24
        total_frames = int(duration * fps)
        
        width, height = 1280, 720
        
        for i in range(total_frames):
            # Crear un degradado de colores que cambia con el tiempo
            r = int(128 + 127 * np.sin(i * 0.02))
            g = int(128 + 127 * np.sin(i * 0.01))
            b = int(128 + 127 * np.sin(i * 0.03))
            
            # Crear imagen con ese color
            img = np.ones((height, width, 3), dtype=np.uint8)
            img[:, :, 0] = r
            img[:, :, 1] = g
            img[:, :, 2] = b
            
            frames.append(img)
        
        # Crear clip con los frames
        clip = ImageClip(frames[0]).set_duration(1/fps)
        for frame in frames[1:]:
            clip = concatenate_videoclips([clip, ImageClip(frame).set_duration(1/fps)])
        
        clip.write_videofile(output_path, fps=fps, codec='libx264')
        return output_path
    except Exception as e:
        logging.error(f"Error al crear fondo básico: {str(e)}")
        return None

# Función de creación de texto
def create_text_image(text, size=(1280, 360), font_size=30, line_height=40, bg_color=(0, 0, 0, 180)):
    # Crear una imagen con canal alfa (transparente)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Crear un rectángulo semi-transparente para el texto
    overlay = Image.new('RGBA', size, bg_color)
    img.paste(overlay, (0, 0), overlay)
    
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)

    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        left, top, right, bottom = draw.textbbox((0, 0), test_line, font=font)
        if right > size[0] - 60:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))

    total_height = len(lines) * line_height
    y = (size[1] - total_height) // 2

    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        x = (size[0] - (right - left)) // 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    return np.array(img)

# Nueva función para crear la imagen de suscripción
def create_subscription_image(logo_url, size=(1280, 720), font_size=60):
    img = Image.new('RGBA', size, (255, 0, 0, 220))  # Fondo rojo semi-transparente
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)

    # Cargar logo del canal
    try:
        response = requests.get(logo_url)
        response.raise_for_status()
        logo_img = Image.open(BytesIO(response.content)).convert("RGBA")
        logo_img = logo_img.resize((100,100))
        logo_position = (20,20)
        img.paste(logo_img,logo_position,logo_img)
    except Exception as e:
        logging.error(f"Error al cargar el logo: {str(e)}")
        
    text1 = "¡SUSCRÍBETE A LECTOR DE SOMBRAS!"
    left1, top1, right1, bottom1 = draw.textbbox((0, 0), text1, font=font)
    x1 = (size[0] - (right1 - left1)) // 2
    y1 = (size[1] - (bottom1 - top1)) // 2 - (bottom1 - top1) // 2 - 20
    draw.text((x1, y1), text1, font=font, fill="white")
    
    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size//2)
    text2 = "Dale like y activa la campana 🔔"
    left2, top2, right2, bottom2 = draw.textbbox((0, 0), text2, font=font2)
    x2 = (size[0] - (right2 - left2)) // 2
    y2 = (size[1] - (bottom2 - top2)) // 2 + (bottom1 - top1) // 2 + 20
    draw.text((x2,y2), text2, font=font2, fill="white")

    return np.array(img)

# Función de creación de video con videos de stock
def create_video_with_stock_backgrounds(texto, nombre_salida, voz, logo_url):
    archivos_temp = []
    clips_audio = []
    clips_finales = []
    background_videos = []
    
    try:
        logging.info("Iniciando proceso de creación de video...")
        frases = [f.strip() + "." for f in texto.split('.') if f.strip()]
        client = texttospeech.TextToSpeechClient()
        
        tiempo_acumulado = 0
        
        # Agrupamos frases en segmentos
        segmentos_texto = []
        segmento_actual = ""
        for frase in frases:
            if len(segmento_actual) + len(frase) < 300:
                segmento_actual += " " + frase
            else:
                segmentos_texto.append(segmento_actual.strip())
                segmento_actual = frase
        segmentos_texto.append(segmento_actual.strip())
        
        # Crear directorio para videos temporales si no existe
        if not os.path.exists("videos/temp"):
            os.makedirs("videos/temp", exist_ok=True)
        
        for i, segmento in enumerate(segmentos_texto):
            logging.info(f"Procesando segmento {i+1} de {len(segmentos_texto)}")
            
            # Generar audio con Google TTS
            synthesis_input = texttospeech.SynthesisInput(text=segmento)
            voice = texttospeech.VoiceSelectionParams(
                language_code="es-ES",
                name=voz,
                ssml_gender=VOCES_DISPONIBLES[voz]
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            retry_count = 0
            max_retries = 3
            
            while retry_count <= max_retries:
                try:
                    response = client.synthesize_speech(
                        input=synthesis_input,
                        voice=voice,
                        audio_config=audio_config
                    )
                    break
                except Exception as e:
                    logging.error(f"Error al solicitar audio (intento {retry_count + 1}): {str(e)}")
                    if "429" in str(e):
                        retry_count += 1
                        time.sleep(2**retry_count)
                    else:
                        raise
            
            if retry_count > max_retries:
                raise Exception("Máximos intentos de reintento alcanzado")
            
            temp_filename = f"videos/temp/audio_{i}.mp3"
            archivos_temp.append(temp_filename)
            with open(temp_filename, "wb") as out:
                out.write(response.audio_content)
            
            audio_clip = AudioFileClip(temp_filename)
            clips_audio.append(audio_clip)
            duracion = audio_clip.duration
            
            # Seleccionar video de stock basado en el contenido del texto
            background_video_path = select_stock_video(segmento, duracion)
            
            if background_video_path and os.path.exists(background_video_path):
                # Si se encontró un video de stock apropiado
                logging.info(f"Usando video de stock: {background_video_path}")
                background_videos.append(background_video_path)
                background_clip = VideoFileClip(background_video_path).resize(height=720)
                
                # Si el video es más corto, lo extendemos con loop
                if background_clip.duration < duracion:
                    n_loops = int(duracion / background_clip.duration) + 1
                    background_clip = background_clip.loop(n=n_loops).subclip(0, duracion)
                else:
                    background_clip = background_clip.subclip(0, duracion)
            else:
                # Si no se encuentra un video, crear uno básico
                logging.info("No se encontró video de stock. Creando fondo básico.")
                basic_bg_path = f"videos/temp/basic_bg_{i}.mp4"
                background_videos.append(basic_bg_path)
                create_basic_background(duracion, basic_bg_path)
                background_clip = VideoFileClip(basic_bg_path)
            
            # Crear capa de texto semi-transparente
            text_img = create_text_image(segmento)
            txt_clip = (ImageClip(text_img)
                      .set_duration(duracion)
                      .set_position(('center', 'bottom')))
            
            # Combinar fondo y texto
            video_segment = CompositeVideoClip([
                background_clip,
                txt_clip
            ]).set_audio(audio_clip)
            
            clips_finales.append(video_segment)
            tiempo_acumulado += duracion
            time.sleep(0.2)

        # Añadir clip de suscripción (con fondo de video si es posible)
        if background_videos and os.path.exists(background_videos[-1]):
            # Usar el último video de fondo generado
            bg_clip = VideoFileClip(background_videos[-1]).resize(height=720).loop(duration=5)
            subscribe_img = create_subscription_image(logo_url)
            subscribe_overlay = ImageClip(subscribe_img).set_duration(5)
            
            subscribe_clip = CompositeVideoClip([bg_clip, subscribe_overlay])
        else:
            # Usar imagen simple si no hay fondos
            subscribe_img = create_subscription_image(logo_url)
            subscribe_clip = ImageClip(subscribe_img).set_duration(5)
        
        clips_finales.append(subscribe_clip)
        
        # Concatenar todos los clips
        video_final = concatenate_videoclips(clips_finales, method="compose")
        
        video_final.write_videofile(
            nombre_salida,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            threads=4
        )
        
        # Cerrar y limpiar todos los recursos
        video_final.close()
        
        for clip in clips_audio:
            clip.close()
        
        for clip in clips_finales:
            clip.close()
            
        # Eliminar archivos temporales
        for temp_file in archivos_temp:
            try:
                if os.path.exists(temp_file):
                    os.close(os.open(temp_file, os.O_RDONLY))
                    os.remove(temp_file)
            except Exception as e:
                logging.error(f"Error al eliminar archivo temporal {temp_file}: {str(e)}")
        
        return True, "Video generado exitosamente"
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        # Cerrar y limpiar recursos en caso de error
        for clip in clips_audio:
            try:
                clip.close()
            except:
                pass
                
        for clip in clips_finales:
            try:
                clip.close()
            except:
                pass
                
        for temp_file in archivos_temp:
            try:
                if os.path.exists(temp_file):
                    os.close(os.open(temp_file, os.O_RDONLY))
                    os.remove(temp_file)
            except:
                pass
        
        return False, str(e)

# Función original (mantenida para compatibilidad)
def create_simple_video(texto, nombre_salida, voz, logo_url):
    # Aquí va tu código original
    # Esta función se mantiene como fallback
    pass

def main():
    st.title("Creador de Videos con Fondos Temáticos")
    
    # Mostrar pestaña para subir videos de stock
    tab1, tab2 = st.tabs(["Generar video", "Administrar videos de stock"])
    
    with tab1:
        uploaded_file = st.file_uploader("Carga un archivo de texto", type="txt")
        voz_seleccionada = st.selectbox("Selecciona la voz", options=list(VOCES_DISPONIBLES.keys()))
        use_stock_videos = st.checkbox("Usar fondos de video temáticos", value=True)
        logo_url = "https://yt3.ggpht.com/pBI3iT87_fX91PGHS5gZtbQi53nuRBIvOsuc-Z-hXaE3GxyRQF8-vEIDYOzFz93dsKUEjoHEwQ=s176-c-k-c0x00ffffff-no-rj"
        
        if uploaded_file:
            texto = uploaded_file.read().decode("utf-8")
            nombre_salida = st.text_input("Nombre del Video (sin extensión)", "video_generado")
            
            if st.button("Generar Video"):
                with st.spinner('Generando video con fondos temáticos... Esto puede tardar varios minutos'):
                    nombre_salida_completo = f"{nombre_salida}.mp4"
                    
                    if use_stock_videos:
                        success, message = create_video_with_stock_backgrounds(texto, nombre_salida_completo, voz_seleccionada, logo_url)
                    else:
                        # Usar el método original sin fondos temáticos
                        success, message = create_simple_video(texto, nombre_salida_completo, voz_seleccionada, logo_url)
                    
                    if success:
                        st.success(message)
                        st.video(nombre_salida_completo)
                        with open(nombre_salida_completo, 'rb') as file:
                            st.download_button(label="Descargar video", data=file, file_name=nombre_salida_completo)
                            
                        st.session_state.video_path = nombre_salida_completo
                    else:
                        st.error(f"Error al generar video: {message}")

            if st.session_state.get("video_path"):
                st.markdown(f'<a href="https://www.youtube.com/upload" target="_blank">Subir video a YouTube</a>', unsafe_allow_html=True)
    
    with tab2:
        st.subheader("Administrar videos de stock")
        
        # Asegurarse que existe el directorio de videos
        if not os.path.exists("videos/stock"):
            os.makedirs("videos/stock", exist_ok=True)
        
        # Mostrar categorías actuales y permitir subir nuevos videos
        selected_category = st.selectbox("Categoría", options=list(VIDEO_CATEGORIES.keys()))
        
        uploaded_stock = st.file_uploader("Subir nuevo video de stock", type=["mp4", "mov", "avi"])
        if uploaded_stock:
            video_name = uploaded_stock.name
            stock_path = f"videos/stock/{selected_category}_{video_name}"
            
            with open(stock_path, "wb") as f:
                f.write(uploaded_stock.getbuffer())
            
            # Actualizar la lista de videos (en producción deberías hacerlo de manera más robusta)
            if selected_category in VIDEO_CATEGORIES:
                VIDEO_CATEGORIES[selected_category].append(stock_path)
            else:
                VIDEO_CATEGORIES[selected_category] = [stock_path]
                
            st.success(f"Video '{video_name}' subido a la categoría '{selected_category}'")
        
        # Mostrar videos actuales en la categoría
        st.subheader(f"Videos en categoría: {selected_category}")
        if selected_category in VIDEO_CATEGORIES and VIDEO_CATEGORIES[selected_category]:
            for video_path in VIDEO_CATEGORIES[selected_category]:
                if os.path.exists(video_path):
                    st.video(video_path)
                    st.text(f"Archivo: {os.path.basename(video_path)}")
                    if st.button(f"Eliminar {os.path.basename(video_path)}", key=video_path):
                        try:
                            os.remove(video_path)
                            VIDEO_CATEGORIES[selected_category].remove(video_path)
                            st.success(f"Video eliminado")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {str(e)}")
        else:
            st.info(f"No hay videos en la categoría '{selected_category}'. Sube algunos videos para comenzar.")


if __name__ == "__main__":
    # Inicializar session state
    if "video_path" not in st.session_state:
        st.session_state.video_path = None
    main()
