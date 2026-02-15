from asyncio import sleep
from pyrogram import Client
from pyrogram.filters import regex
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery, Message

from bot import bot, config_dict, LOGGER
from bot.helper.ext_utils.bot_utils import action
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.modules.mirror_leech import _mirror_leech
from bot.modules.ytdlp import _ytdl


incompte_dict = {}


async def set_incomplte_task(cid, link):
    try:
        msg_id = int(link.split('/')[-1])
        message: Message = await bot.get_messages(cid, msg_id)
        if message.empty:
            return
            
        uid = None
        mesg = message.text.split('\n')
        if len(mesg) > 1 and mesg[1].startswith('Tag: '):
            try:
                id_data = mesg[1].split()[-1]
                uid = int(id_data)
                message.from_user = await bot.get_users(uid)
            except Exception:
                pass

        if not uid and message.reply_to_message:
            if message.reply_to_message.from_user:
                uid = message.reply_to_message.from_user.id
                message.from_user = message.reply_to_message.from_user
                
        if not uid and message.from_user:
            uid = message.from_user.id

        if uid:
            incompte_dict.setdefault(uid, {'msgs': []})
            incompte_dict[uid]['msgs'].append(message)
        else:
            LOGGER.error(f"Could not find User ID for task: {link}")

    except Exception as e:
        LOGGER.error(f"Failed to set incomplete task: {e}")


async def start_resume_task(client: Client, tasks):
    if not isinstance(tasks, list):
        if not incompte_dict:
            LOGGER.info("No incomplete tasks found to auto-resume.")
            return

        for user_id in list(incompte_dict.keys()):
            if data := incompte_dict.get(user_id):
                await start_resume_task(client, data['msgs'])
        if hasattr(tasks, 'message') and tasks.message:
            try:
                await tasks.message.delete()
            except Exception:
                pass
        return
        
    user_id = None
    
    for msg in tasks:
        cmd = action(msg)[1:] + str(config_dict['CMD_SUFFIX'])
        isQbit = isLeech = isYt = False

        def _check_cmd(cmds):
            if any(x == cmd for x in cmds):
                return True
        if _check_cmd(BotCommands.QbMirrorCommand):
            isQbit = True
        elif _check_cmd(BotCommands.LeechCommand):
            isLeech = True
        elif _check_cmd(BotCommands.QbLeechCommand):
            isQbit = isLeech = True
        elif _check_cmd(BotCommands.YtdlCommand):
            isYt = True
        elif _check_cmd(BotCommands.YtdlLeechCommand):
            isLeech = isYt = True
        target_msg = msg.reply_to_message or msg
        message = await sendMessage(target_msg, msg.text)
        message.from_user = msg.from_user
        if not user_id and message.from_user:
            user_id = message.from_user.id
        if isYt:
            _ytdl(client, message, isLeech)
        else:
            _mirror_leech(client, message, isQbit, isLeech)
        await sleep(4)
    if user_id and user_id in incompte_dict:
        del incompte_dict[user_id]


async def resume_task(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data.split()

    if len(data) < 2:
        await query.answer('Invalid action!', show_alert=True)
        return

    action_type = data[1]
    
    if action_type == 'no':
        if user_id in incompte_dict:
            del incompte_dict[user_id]
        await query.answer('Incomplete tasks have been cleared!', show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if action_type == 'yes':
        if tasks := incompte_dict.get(user_id):
            await query.answer("Resuming tasks...")
            await start_resume_task(client, tasks['msgs'])
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer('You don\'t have incomplete tasks to resume!', show_alert=True)


bot.add_handler(CallbackQueryHandler(resume_task, filters=regex('^resume (yes|no)')))
