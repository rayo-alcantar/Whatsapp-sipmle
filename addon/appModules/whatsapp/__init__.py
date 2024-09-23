# -*- coding: utf-8 -*-
# Complemento simplificado para NVDA enfocado en WhatsApp.
# Proporciona funcionalidades básicas sin configuraciones adicionales.
#Créditos y código en algunas opciones sacadas del comlemento de Gerardo Kessler y Kostya Gladkiy
 #Angel Alcantar.
 
from threading import Thread
from time import sleep
import speech
from scriptHandler import script
import api
import re
import appModuleHandler
import ui  # Importar el módulo ui para utilizar la función message
import controlTypes
from keyboardHandler import KeyboardInputGesture

icon_from_context_menu = {
	"reply to message": "\ue97a",
	"edit message": "\ue70f",
	"react": "\ue76e",
	"forward message": "\uee35",
	"delete": "\ue74d",
	"mark as read": "\ue8bd",
	"mark as unread": "\ue668",
	"leave the group": "\ue89b",
	"star message": "\ue734",
	"remove from starred messages": "\ue735",
	"save as": "\ue74e",
	"select message": "\ue73a",
}

# Función para silenciar el sintetizador durante un tiempo especificado
def mute(time):
	Thread(target=killSpeak, args=(time,), daemon=True).start()

def killSpeak(time):
	if speech.getState().speechMode != speech.SpeechMode.talk:
		return
	speech.setSpeechMode(speech.SpeechMode.off)
	sleep(time)
	speech.setSpeechMode(speech.SpeechMode.talk)

class AppModule(appModuleHandler.AppModule):
	category = "whatsapp"

	def __init__(self, *args, **kwargs):
		super(AppModule, self).__init__(*args, **kwargs)
		self.execute_context_menu_option = None  # Ahora es un atributo de instancia.
		self.message_box_element = None
		self.last_focus_message_element = None

	def event_NVDAObject_init(self, obj):
		# Eliminar números de teléfono de los nombres de los chats
		if '+' in obj.name:
			obj.name = re.sub(r'\+\d[\d\s\:\~\&-]{12,}', '', obj.name)
		
		# Detectar y marcar mensajes reenviados
		if getattr(obj, 'UIAAutomationId', False) == 'BubbleListItem':
			for element in obj.children:
				if getattr(element, 'UIAAutomationId', False) == 'ForwardedHeader':
					obj.name = f"Reenviado: {obj.name}"
					break  # Evita agregar múltiples prefijos si hay varios 'ForwardedHeader'
	def activate_option_for_menu(self, option):
		obj = api.getFocusObject()
		if not obj or obj.UIAAutomationId not in ("BubbleListItem", "ChatsListItem"):
			return
		if self.execute_context_menu_option:
			return
		if isinstance(option, str):
			option = (option,)
		self.execute_context_menu_option = option
		# Enviar la tecla 'Aplicaciones' para abrir el menú contextual
		KeyboardInputGesture.fromName("applications").send()

	def event_gainFocus(self, obj, nextHandler):
		if self.execute_context_menu_option:
			# Ajuste para manejar el menú de emojis si está presente
			if obj.parent.UIAAutomationId == "EmojiList":
				obj = obj.parent.parent
			try:
				# Buscar el botón correcto en el menú contextual
				targetButton = next(
					(
						item for item in obj.parent.children
						if hasattr(item, 'firstChild') and item.firstChild and item.firstChild.name in self.execute_context_menu_option
					),
					None
				)
			except Exception as e:
				ui.message(f"Error al buscar la opción en el menú contextual: {e}")
				targetButton = None
			self.execute_context_menu_option = None
			if targetButton:
				targetButton.doAction()
			else:
				# Si no se encuentra la opción, cerrar el menú contextual
				ui.message("No se encontró la opción en el menú contextual.")
				KeyboardInputGesture.fromName("escape").send()
			return
		nextHandler()

	@script(
		description="Eliminar un mensaje o chat",
		gesture="kb:alt+delete",
		category=category
	)
	def script_deletion(self, gesture):
		self.activate_option_for_menu(icon_from_context_menu["delete"])

	@script(
		description="Editar un mensaje",
		gesture="kb:alt+e",
		category=category
	)
	def script_edit_message(self, gesture):
		self.activate_option_for_menu(icon_from_context_menu["edit message"])

	@script(
		description='Inicia o finaliza la grabación de un mensaje de voz',
		gesture='kb:control+r',
		category=category
	)
	def script_voiceMessage(self, gesture):
		send = self.get('SendVoiceMessageButton', False)
		if send:
			send.doAction()
			mute(0.1)
			return
		record = self.get('RightButton', True)
		if record:
			if record.previous.description == '':
				record.doAction()
				mute(1)
			else:
				ui.message('El cuadro de edición no está vacío')

	@script(
		description='Decir el nombre del chat actual',
		gesture='kb:control+shift+t',
		category=category
	)
	def script_chatName(self, gesture):
		title = self.get('TitleButton', True)
		if title:
			contact_name = ' '.join([obj.name for obj in title.children if len(obj.name) < 50])
			ui.message(contact_name)

	@script(
		description='Mover entre la lista de mensajes y el cuadro de texto',
		gesture='kb:alt+leftArrow',
		category=category
	)
	def script_switchMessagesAndInput(self, gesture):
		# Obtener el objeto actualmente enfocado
		obj = api.getFocusObject()
		if obj.UIAAutomationId == "InputBarTextBox" and self.last_focus_message_element:
			# Si el foco está en el cuadro de texto y hay un mensaje previo, volver al mensaje
			try:
				if self.last_focus_message_element.location:
					self.last_focus_message_element.setFocus()
				else:
					raise Exception("El mensaje anterior ya no está disponible")
			except Exception as e:
				ui.message("No se pudo regresar al mensaje anterior: {}".format(e))
				# Intentar enfocar el último mensaje en la lista
				messages_list = self.get_messages_element()
				if messages_list and messages_list.lastChild:
					messages_list.lastChild.setFocus()
				else:
					ui.message("No se pudo encontrar ningún mensaje para enfocar")
			return
		# Intentar obtener el cuadro de texto almacenado
		message_box = self.message_box_element
		if not message_box or not message_box.location:
			# Si no está almacenado o no es válido, buscarlo nuevamente
			message_box = next((item for item in self.get_elements() if item.UIAAutomationId == "InputBarTextBox"), None)
			if message_box:
				self.message_box_element = message_box
			else:
				ui.message("No se pudo encontrar el cuadro de texto")
				return
		try:
			# Almacenar el último mensaje con foco antes de cambiar al cuadro de texto
			if obj.UIAAutomationId == "BubbleListItem":
				self.last_focus_message_element = obj
			# Establecer el foco en el cuadro de texto
			message_box.setFocus()
		except Exception as e:
			self.message_box_element = None
			ui.message("Error al establecer el foco en el cuadro de texto: {}".format(e))

	def get_elements(self):
		try:
			return api.getForegroundObject().children[1].firstChild.children
		except (AttributeError, IndexError):
			return []

	@script(
		description='Ir a la etiqueta de mensajes no leídos',
		gesture='kb:alt+downArrow',
		category=category
	)
	def script_unreadFocus(self, gesture):
		messagesObject = self.get('MessagesList', False)
		if not messagesObject:
			return
		for obj in reversed(messagesObject.children):
			if obj.childCount == 1 and obj.firstChild.UIAAutomationId == '' and re.search(r'\d{1,3}\s\w+', obj.name):
				obj.setFocus()
				break

	def get(self, id, errorMessage, gesture=None):
		try:
			elements = self.get_elements()
			for obj in elements:
				if getattr(obj, 'UIAAutomationId', '') == id:
					return obj
		except (IndexError, AttributeError):
			pass  # Manejo de posibles errores en la jerarquía de objetos.

		if errorMessage:
			ui.message('Elemento no encontrado')

		if gesture:
			gesture.send()

	@script(
		category=category,
		description='Muestra el mensaje original en una ventana explorable',
		gesture='kb:alt+c'
	)
	def script_showOriginalMessage(self, gesture):
		# Obtener el objeto actualmente enfocado
		focus = api.getFocusObject()

		# Verificar que el objeto tiene el rol LISTITEM y está enfocado
		if focus.role == controlTypes.Role.LISTITEM and focus.isFocusable and focus.hasFocus:
			try:
				# Intentar obtener el contenido del mensaje buscando en los hijos
				original_text_list = []
				for item in focus.children:
					if item.UIAAutomationId == 'TextBlock' and item.name:
						original_text_list.append(item.name)

				# Unir el texto si se encontró
				original_text = '\n'.join(original_text_list)

				if original_text:
					# Mostrar el mensaje original en una ventana explorable
					ui.browseableMessage(original_text, 'Mensaje original')
				else:
					ui.message('No hay texto para mostrar')
			except Exception as e:
				# Informar el error en caso de excepción
				ui.message('Error al obtener el mensaje original: {}'.format(str(e)))
		else:
			ui.message('El objeto actual no es un mensaje o no tiene el foco.')

	@script(
		category=category,
		description="Abre la información para el chat actual",
		gesture='kb:alt+i'
	)
	def script_chat_info(self, gesture):
		chat_info = self.get("TitleButton", True)
		if chat_info:
			chat_info.doAction()
		else:
			ui.message("No se encontró el botón")

	@script(
		description='Ir a la lista de mensajes',
		gesture='kb:control+alt+leftArrow',
		category=category
	)
	def script_toMessageList(self, gesture):
		obj = api.getFocusObject()
		if obj.UIAAutomationId == "BubbleListItem":
			ui.message(obj.name)
			return
		messages_list = self.get_messages_element()
		if not messages_list:
			ui.message("No se encontró la lista de mensajes")
			return
		try:
			# Movemos el foco al último mensaje de la lista
			last_message = messages_list.lastChild
			if last_message:
				last_message.setFocus()
				self.last_focus_message_element = last_message
			else:
				ui.message("La lista de mensajes está vacía")
		except Exception as e:
			ui.message("Error al acceder a la lista de mensajes: {}".format(e))

	def get_messages_element(self):
		elements = self.get_elements()
		for item in elements:
			if item.UIAAutomationId == "MessagesList":
				return item
		return None

	@script(
		description='Ir a la lista de chats',
		gesture='kb:alt+rightArrow',
		category=category
	)
	def script_toChatList(self, gesture):
		obj = api.getFocusObject()
		if obj.UIAAutomationId == "ChatsListItem":
			ui.message(obj.name)
			return
		chats_list = self.get_chats_element()
		if not chats_list:
			ui.message("No se encontró la lista de chats")
			return
		try:
			# Movemos el foco al primer chat de la lista
			first_chat = chats_list.firstChild
			if first_chat:
				first_chat.setFocus()
				self.last_focus_chat_element = first_chat
			else:
				ui.message("La lista de chats está vacía")
		except Exception as e:
			ui.message("Error al acceder a la lista de chats: {}".format(e))

	def get_chats_element(self):
		elements = self.get_elements()
		for item in elements:
			if item.UIAAutomationId == "ChatList":
				return item
		return None

	# Definición de gestos adicionales
	__gestures = {
		"kb:control+alt+leftArrow": "script_toMessageList",
		"kb:alt+rightArrow": "script_toChatList",
	}
