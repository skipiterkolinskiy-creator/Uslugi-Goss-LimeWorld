import asyncio, os, logging, secrets, string
from datetime import datetime
from html import escape
from pathlib import Path
import gspread
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMIN_CHAT_ID=int(os.getenv('ADMIN_CHAT_ID','0'))
ADMIN_IDS={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
SPREADSHEET_ID=os.getenv('SPREADSHEET_ID','').strip()
CREDS=os.getenv('GOOGLE_CREDENTIALS_FILE','credentials.json')
CITIZENS_SHEET=os.getenv('CITIZENS_SHEET','Граждане')
REQUESTS_SHEET=os.getenv('REQUESTS_SHEET','Заявки')
MEDICAL_SHEET=os.getenv('MEDICAL_SHEET','Медкарты')
LOGS_SHEET=os.getenv('LOGS_SHEET','Логи')

if not BOT_TOKEN or not ADMIN_CHAT_ID or not SPREADSHEET_ID: raise RuntimeError('Проверьте .env')
if not Path(CREDS).exists(): raise RuntimeError(f'Не найден {CREDS}')

logging.basicConfig(level=logging.INFO)
router=Router()

class Reg(StatesGroup):
    fio=State(); age=State(); birth=State(); sex=State(); c1=State(); c2=State(); nation=State(); skin=State(); hair=State(); eyes=State(); appearance=State(); military=State(); photo=State()
class Med(StatesGroup):
    height=State(); weight=State(); blood=State(); allergies=State(); chronic=State(); notes=State()
class Reject(StatesGroup): reason=State()

MENU=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='👤 Мой персонаж'),KeyboardButton(text='🆕 Регистрация')],[KeyboardButton(text='🩺 Медкарта'),KeyboardButton(text='📄 Документы')],[KeyboardButton(text='💸 Штрафы'),KeyboardButton(text='🚨 Розыск')]],resize_keyboard=True)
CANCEL=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='❌ Отмена')]],resize_keyboard=True)
SEX=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Мужчина'),KeyboardButton(text='Женщина')],[KeyboardButton(text='❌ Отмена')]],resize_keyboard=True)
YESNO=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Да'),KeyboardButton(text='Нет')],[KeyboardButton(text='❌ Отмена')]],resize_keyboard=True)

def now(): return datetime.now().strftime('%d.%m.%Y %H:%M:%S')
def book(): return gspread.service_account(filename=CREDS).open_by_key(SPREADSHEET_ID)
def sheet(name, headers):
    b=book()
    try: ws=b.worksheet(name)
    except gspread.WorksheetNotFound:
        ws=b.add_worksheet(title=name,rows=1000,cols=max(20,len(headers))); ws.append_row(headers)
    if not ws.row_values(1): ws.append_row(headers)
    return ws

def setup():
    sheet(CITIZENS_SHEET,['Паспорт','Код входа','Telegram ID','Username','Фамилия','Имя','Отчество','Возраст','Дата рождения','Пол','Первое гражданство','Второе гражданство','Национальность','Цвет кожи','Цвет волос','Цвет глаз','Описание внешности','Военный билет','Фото file_id','Статус','Розыск','Штрафы','Лицензии','Дата регистрации'])
    sheet(REQUESTS_SHEET,['ID заявки','Тип','Telegram ID','Username','ФИО','Данные','Статус','Причина отказа','Создано','Рассмотрено'])
    sheet(MEDICAL_SHEET,['Паспорт','Telegram ID','Рост','Вес','Группа крови','Аллергии','Хронические заболевания','Примечания','Статус','Дата'])
    sheet(LOGS_SHEET,['Дата','Администратор ID','Действие','Объект','Подробности'])

def allrows(name): return sheet(name,['']).get_all_records()
def next_num(name,col,default):
    vals=sheet(name,[col]).col_values(1)[1:]; nums=[]
    for v in vals:
        try: nums.append(int(str(v).replace('№','').strip()))
        except: pass
    return max(nums,default=default)+1

def citizen_tg(uid):
    for r in allrows(CITIZENS_SHEET):
        if str(r.get('Telegram ID',''))==str(uid): return r

def find_request(rid):
    ws=sheet(REQUESTS_SHEET,['ID заявки'])
    for i,r in enumerate(ws.get_all_records(),2):
        if str(r.get('ID заявки'))==str(rid): return ws,i,r
    return None,None,None

def split_fio(fio):
    p=fio.split(); return (p[0] if p else '', p[1] if len(p)>1 else '', ' '.join(p[2:]) if len(p)>2 else '')

def adminkb(rid,typ,uid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Одобрить',callback_data=f'a:{typ}:{rid}:{uid}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'r:{typ}:{rid}:{uid}')],[InlineKeyboardButton(text='⚫ Мёртв',callback_data=f'd:{uid}'),InlineKeyboardButton(text='🟢 Жив',callback_data=f'l:{uid}')]])

def upd_status(uid,status):
    ws=sheet(CITIZENS_SHEET,['Telegram ID']); rows=ws.get_all_records(); hdr=ws.row_values(1)
    if 'Telegram ID' not in hdr or 'Статус' not in hdr: return False
    c=hdr.index('Статус')+1
    for i,r in enumerate(rows,2):
        if str(r.get('Telegram ID',''))==str(uid): ws.update_cell(i,c,status); return True
    return False

def log(admin,action,obj,details=''): sheet(LOGS_SHEET,['Дата']).append_row([now(),admin,action,obj,details])

@router.message(CommandStart())
async def start(m:Message,state:FSMContext):
    await state.clear(); c=await asyncio.to_thread(citizen_tg,m.from_user.id)
    if c: await m.answer(f"<b>УслугиГосс</b>\n\nВы вошли как <b>{escape(c.get('Фамилия',''))} {escape(c.get('Имя',''))}</b>\nПаспорт №{escape(str(c.get('Паспорт','—')))}",reply_markup=MENU)
    else: await m.answer('<b>УслугиГосс</b>\n\nПерсонаж на этом аккаунте не найден. Создайте нового персонажа.',reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🆕 Регистрация')]],resize_keyboard=True))

@router.message(F.text=='❌ Отмена')
async def cancel(m,state): await state.clear(); await m.answer('Отменено.',reply_markup=MENU)

@router.message(F.text=='🆕 Регистрация')
async def reg0(m,state):
    if await asyncio.to_thread(citizen_tg,m.from_user.id): return await m.answer('Персонаж уже зарегистрирован.')
    await state.set_state(Reg.fio); await m.answer('Введите Фамилию Имя Отчество:',reply_markup=CANCEL)
@router.message(Reg.fio)
async def reg1(m,state):
    if len((m.text or '').split())<2: return await m.answer('Введите минимум фамилию и имя.')
    await state.update_data(fio=m.text.strip()); await state.set_state(Reg.age); await m.answer('Возраст персонажа:')
@router.message(Reg.age)
async def reg2(m,state):
    t=(m.text or '').strip()
    if not t.isdigit() or not 14<=int(t)<=200: return await m.answer('Возраст от 14 до 200.')
    await state.update_data(age=int(t)); await state.set_state(Reg.birth); await m.answer('Дата рождения ДД.ММ.ГГГГ:')
@router.message(Reg.birth)
async def reg3(m,state):
    try: datetime.strptime((m.text or '').strip(),'%d.%m.%Y')
    except: return await m.answer('Пример: 27.06.2001')
    await state.update_data(birth=m.text.strip()); await state.set_state(Reg.sex); await m.answer('Пол:',reply_markup=SEX)
@router.message(Reg.sex)
async def reg4(m,state):
    if m.text not in {'Мужчина','Женщина'}: return await m.answer('Выберите кнопкой.')
    await state.update_data(sex=m.text); await state.set_state(Reg.c1); await m.answer('Первое гражданство:',reply_markup=CANCEL)
@router.message(Reg.c1)
async def reg5(m,state): await state.update_data(c1=m.text.strip()); await state.set_state(Reg.c2); await m.answer('Второе и последующие гражданства через запятую, либо Нет:')
@router.message(Reg.c2)
async def reg6(m,state): await state.update_data(c2=m.text.strip()); await state.set_state(Reg.nation); await m.answer('Национальность:')
@router.message(Reg.nation)
async def reg7(m,state): await state.update_data(nation=m.text.strip()); await state.set_state(Reg.skin); await m.answer('Цвет кожи:')
@router.message(Reg.skin)
async def reg8(m,state): await state.update_data(skin=m.text.strip()); await state.set_state(Reg.hair); await m.answer('Цвет волос:')
@router.message(Reg.hair)
async def reg9(m,state): await state.update_data(hair=m.text.strip()); await state.set_state(Reg.eyes); await m.answer('Цвет глаз:')
@router.message(Reg.eyes)
async def reg10(m,state): await state.update_data(eyes=m.text.strip()); await state.set_state(Reg.appearance); await m.answer('Описание внешности:')
@router.message(Reg.appearance)
async def reg11(m,state):
    await state.update_data(appearance=m.text.strip()); d=await state.get_data()
    if d['age']<18:
        await state.update_data(military='Не предусмотрен по возрасту'); await state.set_state(Reg.photo); await m.answer('Отправьте фото персонажа для документов.',reply_markup=CANCEL)
    else:
        await state.set_state(Reg.military); await m.answer('Есть военный билет?',reply_markup=YESNO)
@router.message(Reg.military)
async def reg12(m,state):
    if m.text not in {'Да','Нет'}: return await m.answer('Выберите Да или Нет.')
    await state.update_data(military=m.text); await state.set_state(Reg.photo); await m.answer('Отправьте фото персонажа для документов.',reply_markup=CANCEL)
@router.message(Reg.photo)
async def reg13(m,state,bot:Bot):
    if not m.photo: return await m.answer('Нужно фото.')
    d=await state.get_data(); rid=await asyncio.to_thread(next_num,REQUESTS_SHEET,'ID заявки',0); fio=d['fio']; photo=m.photo[-1].file_id
    data=f"ФИО: {fio}\nВозраст: {d['age']}\nДата рождения: {d['birth']}\nПол: {d['sex']}\nГражданство: {d['c1']}\nДоп. гражданство: {d['c2']}\nНациональность: {d['nation']}\nЦвет кожи: {d['skin']}\nВолосы: {d['hair']}\nГлаза: {d['eyes']}\nВнешность: {d['appearance']}\nВоенный билет: {d['military']}\nФото file_id: {photo}"
    await asyncio.to_thread(sheet(REQUESTS_SHEET,['ID заявки']).append_row,[rid,'Паспорт',m.from_user.id,m.from_user.username or '',fio,data,'На рассмотрении','',now(),''])
    await bot.send_photo(ADMIN_CHAT_ID,photo,caption=f"<b>ЗАЯВКА НА ПАСПОРТ #{rid}</b>\n\n{escape(data)}",reply_markup=adminkb(rid,'Паспорт',m.from_user.id))
    await state.clear(); await m.answer(f'Заявка #{rid} отправлена администраторам.',reply_markup=MENU)

@router.message(F.text=='🩺 Медкарта')
async def med0(m,state):
    if not await asyncio.to_thread(citizen_tg,m.from_user.id): return await m.answer('Сначала получите паспорт.')
    await state.set_state(Med.height); await m.answer('Рост:',reply_markup=CANCEL)
@router.message(Med.height)
async def med1(m,state): await state.update_data(height=m.text); await state.set_state(Med.weight); await m.answer('Вес:')
@router.message(Med.weight)
async def med2(m,state): await state.update_data(weight=m.text); await state.set_state(Med.blood); await m.answer('Группа крови:')
@router.message(Med.blood)
async def med3(m,state): await state.update_data(blood=m.text); await state.set_state(Med.allergies); await m.answer('Аллергии или Нет:')
@router.message(Med.allergies)
async def med4(m,state): await state.update_data(allergies=m.text); await state.set_state(Med.chronic); await m.answer('Хронические заболевания или Нет:')
@router.message(Med.chronic)
async def med5(m,state): await state.update_data(chronic=m.text); await state.set_state(Med.notes); await m.answer('Примечания или Нет:')
@router.message(Med.notes)
async def med6(m,state,bot:Bot):
    d=await state.get_data(); c=await asyncio.to_thread(citizen_tg,m.from_user.id); rid=await asyncio.to_thread(next_num,REQUESTS_SHEET,'ID заявки',0)
    data=f"Паспорт: {c['Паспорт']}\nФИО: {c['Фамилия']} {c['Имя']} {c['Отчество']}\nРост: {d['height']}\nВес: {d['weight']}\nГруппа крови: {d['blood']}\nАллергии: {d['allergies']}\nХронические заболевания: {d['chronic']}\nПримечания: {m.text}"
    await asyncio.to_thread(sheet(REQUESTS_SHEET,['ID заявки']).append_row,[rid,'Медкарта',m.from_user.id,m.from_user.username or '',f"{c['Фамилия']} {c['Имя']}",data,'На рассмотрении','',now(),''])
    await bot.send_message(ADMIN_CHAT_ID,f"<b>ЗАЯВКА НА МЕДКАРТУ #{rid}</b>\n\n{escape(data)}",reply_markup=adminkb(rid,'Медкарта',m.from_user.id))
    await state.clear(); await m.answer(f'Медкарта отправлена. Заявка #{rid}.',reply_markup=MENU)

@router.message(F.text=='👤 Мой персонаж')
async def me(m):
    c=await asyncio.to_thread(citizen_tg,m.from_user.id)
    if not c: return await m.answer('Персонаж не найден.')
    await m.answer(f"<b>Паспорт:</b> №{c.get('Паспорт','—')}\n<b>ФИО:</b> {escape(c.get('Фамилия',''))} {escape(c.get('Имя',''))} {escape(c.get('Отчество',''))}\n<b>Статус:</b> {escape(str(c.get('Статус','—')))}\n<b>Розыск:</b> {escape(str(c.get('Розыск','Нет')))}\n<b>Штрафы:</b> {escape(str(c.get('Штрафы','Нет')))}\n<b>Лицензии:</b> {escape(str(c.get('Лицензии','Нет')))}")
@router.message(F.text=='💸 Штрафы')
async def fines(m):
    c=await asyncio.to_thread(citizen_tg,m.from_user.id)
    if not c:return await m.answer('Персонаж не найден.')
    await m.answer(f"<b>Штрафы:</b> {escape(str(c.get('Штрафы','Нет')))}\n\nОплата через /donate. Поддельный скрин: x2 штраф и розыск.")
@router.message(F.text=='🚨 Розыск')
async def wanted(m):
    c=await asyncio.to_thread(citizen_tg,m.from_user.id)
    await m.answer(f"<b>Розыск:</b> {escape(str(c.get('Розыск','Нет'))) if c else 'Персонаж не найден'}")
@router.message(F.text=='📄 Документы')
async def docs(m):
    c=await asyncio.to_thread(citizen_tg,m.from_user.id)
    if not c:return await m.answer('Персонаж не найден.')
    await m.answer(f"Паспорт №{c.get('Паспорт','—')}\nВоенный билет: {escape(str(c.get('Военный билет','—')))}\nЛицензии: {escape(str(c.get('Лицензии','Нет')))}")

@router.callback_query(F.data.startswith('a:'))
async def approve(cb:CallbackQuery,bot:Bot):
    if cb.from_user.id not in ADMIN_IDS:return await cb.answer('Нет доступа',show_alert=True)
    _,typ,rid,uid=cb.data.split(':'); ws,i,r=await asyncio.to_thread(find_request,int(rid))
    if not r:return await cb.answer('Не найдено',show_alert=True)
    d={}
    for line in str(r['Данные']).splitlines():
        if ':' in line:
            k,v=line.split(':',1); d[k.strip()]=v.strip()
    if typ=='Паспорт':
        p=await asyncio.to_thread(next_num,CITIZENS_SHEET,'Паспорт',613); code=f"UG-{p}-{secrets.token_hex(2).upper()}"; s,n,o=split_fio(d.get('ФИО',''))
        await asyncio.to_thread(sheet(CITIZENS_SHEET,['Паспорт']).append_row,[p,code,int(uid),r.get('Username',''),s,n,o,d.get('Возраст',''),d.get('Дата рождения',''),d.get('Пол',''),d.get('Гражданство',''),d.get('Доп. гражданство',''),d.get('Национальность',''),d.get('Цвет кожи',''),d.get('Волосы',''),d.get('Глаза',''),d.get('Внешность',''),d.get('Военный билет',''),d.get('Фото file_id',''),'Жив','Нет','Нет','Нет',now()])
        await bot.send_message(int(uid),f"✅ Паспорт одобрен. Номер №{p}\nКод входа: <code>{code}</code>")
    else:
        await asyncio.to_thread(sheet(MEDICAL_SHEET,['Паспорт']).append_row,[d.get('Паспорт',''),int(uid),d.get('Рост',''),d.get('Вес',''),d.get('Группа крови',''),d.get('Аллергии',''),d.get('Хронические заболевания',''),d.get('Примечания',''),'Одобрено',now()])
        await bot.send_message(int(uid),'✅ Медкарта одобрена.')
    await asyncio.to_thread(ws.update_cell,i,7,'Одобрено'); await asyncio.to_thread(ws.update_cell,i,10,now()); await asyncio.to_thread(log,cb.from_user.id,'Одобрение',f'Заявка #{rid}',typ)
    await cb.message.edit_reply_markup(reply_markup=None); await cb.answer('Одобрено')

@router.callback_query(F.data.startswith('r:'))
async def reject0(cb,state):
    if cb.from_user.id not in ADMIN_IDS:return await cb.answer('Нет доступа',show_alert=True)
    _,typ,rid,uid=cb.data.split(':'); await state.set_state(Reject.reason); await state.update_data(rid=rid,uid=uid); await cb.message.reply(f'Причина отказа по заявке #{rid}:'); await cb.answer()
@router.message(Reject.reason)
async def reject1(m,state,bot:Bot):
    if m.from_user.id not in ADMIN_IDS:return
    d=await state.get_data(); ws,i,r=await asyncio.to_thread(find_request,int(d['rid']))
    await asyncio.to_thread(ws.update_cell,i,7,'Отклонено'); await asyncio.to_thread(ws.update_cell,i,8,m.text); await asyncio.to_thread(ws.update_cell,i,10,now())
    await bot.send_message(int(d['uid']),f"❌ Заявка #{d['rid']} отклонена.\nПричина: {escape(m.text)}"); await asyncio.to_thread(log,m.from_user.id,'Отклонение',f"Заявка #{d['rid']}",m.text); await state.clear(); await m.answer('Отказ отправлен.')

@router.callback_query(F.data.startswith('d:'))
async def dead(cb,bot:Bot):
    if cb.from_user.id not in ADMIN_IDS:return await cb.answer('Нет доступа',show_alert=True)
    uid=int(cb.data.split(':')[1]); ok=await asyncio.to_thread(upd_status,uid,'Мёртв')
    if ok: await bot.send_message(uid,'⚫ Персонаж отмечен как мёртвый.'); await asyncio.to_thread(log,cb.from_user.id,'Статус',uid,'Мёртв')
    await cb.answer('Готово' if ok else 'Не найдено',show_alert=not ok)
@router.callback_query(F.data.startswith('l:'))
async def alive(cb,bot:Bot):
    if cb.from_user.id not in ADMIN_IDS:return await cb.answer('Нет доступа',show_alert=True)
    uid=int(cb.data.split(':')[1]); ok=await asyncio.to_thread(upd_status,uid,'Жив')
    if ok: await bot.send_message(uid,'🟢 Статус персонажа: Жив.'); await asyncio.to_thread(log,cb.from_user.id,'Статус',uid,'Жив')
    await cb.answer('Готово' if ok else 'Не найдено',show_alert=not ok)

async def main():
    await asyncio.to_thread(setup)
    bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(storage=MemoryStorage()); dp.include_router(router); await bot.delete_webhook(drop_pending_updates=True)
    try: await bot.send_message(ADMIN_CHAT_ID,f'🟢 <b>УслугиГосс запущен</b>\n{now()}')
    except Exception: logging.exception('ADMIN_CHAT_ID')
    await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())
