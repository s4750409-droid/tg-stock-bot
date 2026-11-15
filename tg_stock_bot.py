import json
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

# ====================== НАСТРОЙКИ ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # берётся из переменных окружения на хостинге
ADMIN_IDS = [8104786287, 9222897621]  # ваши два ID
DATA_FILE = "data.json"
# =======================================================

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен! Добавь его в переменные окружения.")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# ------------------ Хранилище ------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"items": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ------------------ Клавиатуры ------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Список вещей", callback_data="list_items")],
        [InlineKeyboardButton(text="➕ Добавить вещь", callback_data="add_item")],
    ])

def items_list_kb(items: dict):
    buttons = []
    for name in sorted(items.keys()):
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"item:{name}")])
    buttons.append([InlineKeyboardButton(text="« В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def item_actions_kb(name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➖ Уменьшить количество", callback_data=f"decrease:{name}")],
        [InlineKeyboardButton(text="🗑 Удалить вещь", callback_data=f"delete:{name}")],
        [InlineKeyboardButton(text="« Назад к списку", callback_data="list_items")],
    ])

def sizes_kb(name: str, sizes: dict):
    buttons = []
    for size, qty in sorted(sizes.items(), key=lambda x: str(x[0])):
        buttons.append([InlineKeyboardButton(
            text=f"{size} — {qty} шт",
            callback_data=f"dec_size:{name}:{size}"
        )])
    buttons.append([InlineKeyboardButton(text="« Назад", callback_data=f"item:{name}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def amount_kb(name: str, size: str, max_qty: int):
    buttons = []
    row = []
    for i in range(1, min(6, max_qty + 1)):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"do_dec:{name}:{size}:{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if max_qty > 5:
        buttons.append([InlineKeyboardButton(text="Все", callback_data=f"do_dec:{name}:{size}:{max_qty}")])
    buttons.append([InlineKeyboardButton(text="« Назад", callback_data=f"decrease:{name}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ------------------ FSM ------------------
class AddItem(StatesGroup):
    waiting_name = State()
    waiting_sizes = State()

# ------------------ Хендлеры ------------------
@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "Привет! Это бот учёта вещей.\n\nВыберите действие:",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "list_items")
async def list_items(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = load_data()
    items = data.get("items", {})

    if not items:
        await callback.message.edit_text(
            "Пока нет ни одной вещи.\nНажми «Добавить вещь».",
            reply_markup=main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Выбери вещь:",
            reply_markup=items_list_kb(items)
        )
    await callback.answer()

@router.callback_query(F.data.startswith("item:"))
async def show_item(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    name = callback.data.split(":", 1)[1]
    data = load_data()
    item = data.get("items", {}).get(name)

    if not item:
        await callback.answer("Вещь не найдена", show_alert=True)
        return

    sizes = item.get("sizes", {})
    text = f"<b>{name}</b>\n\n"
    if not sizes:
        text += "Размеры не указаны"
    else:
        for size, qty in sorted(sizes.items(), key=lambda x: str(x[0])):
            text += f"• {size} — <b>{qty}</b> шт\n"

    await callback.message.edit_text(
        text,
        reply_markup=item_actions_kb(name),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

# ---------- Добавление вещи ----------
@router.callback_query(F.data == "add_item")
async def add_item_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AddItem.waiting_name)
    await callback.message.edit_text(
        "Введи название вещи:\n\n"
        "Пример: <code>Nike Air Max 90</code>\n\n"
        "Или нажми /cancel чтобы отменить",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.message(AddItem.waiting_name)
async def add_item_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуй ещё раз:")
        return

    data = load_data()
    if name in data.get("items", {}):
        await message.answer("Такая вещь уже есть. Введи другое название или /cancel")
        return

    await state.update_data(name=name)
    await state.set_state(AddItem.waiting_sizes)
    await message.answer(
        f"Название: <b>{name}</b>\n\n"
        "Теперь введи размеры и количество в формате:\n"
        "<code>42:3 43:5 44:1</code>\n\n"
        "Можно писать через пробел или с новой строки.\n"
        "Пример: <code>S:2 M:4 L:1 XL:3</code>\n\n"
        "/cancel — отмена",
        parse_mode=ParseMode.HTML
    )

@router.message(AddItem.waiting_sizes)
async def add_item_sizes(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip().replace("\n", " ")
    sizes = {}

    try:
        parts = text.split()
        for part in parts:
            if ":" not in part:
                raise ValueError
            size, qty = part.split(":", 1)
            size = size.strip()
            qty = int(qty.strip())
            if qty < 0:
                raise ValueError
            sizes[size] = qty
    except Exception:
        await message.answer(
            "Неправильный формат.\n"
            "Нужно так: <code>42:3 43:5 44:1</code>\n\n"
            "Попробуй ещё раз или /cancel",
            parse_mode=ParseMode.HTML
        )
        return

    if not sizes:
        await message.answer("Нужно указать хотя бы один размер. Попробуй ещё раз:")
        return

    data = await state.get_data()
    name = data["name"]

    db = load_data()
    db.setdefault("items", {})[name] = {"sizes": sizes}
    save_data(db)

    await state.clear()

    sizes_text = "\n".join([f"• {s} — {q} шт" for s, q in sorted(sizes.items(), key=lambda x: str(x[0]))])
    await message.answer(
        f"✅ Вещь добавлена!\n\n"
        f"<b>{name}</b>\n{sizes_text}",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML
    )

# ---------- Уменьшение количества ----------
@router.callback_query(F.data.startswith("decrease:"))
async def decrease_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    name = callback.data.split(":", 1)[1]
    data = load_data()
    item = data.get("items", {}).get(name)

    if not item or not item.get("sizes"):
        await callback.answer("Нет размеров", show_alert=True)
        return

    await callback.message.edit_text(
        f"Выбери размер для <b>{name}</b>:",
        reply_markup=sizes_kb(name, item["sizes"]),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.callback_query(F.data.startswith("dec_size:"))
async def decrease_choose_amount(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    _, name, size = callback.data.split(":", 2)
    data = load_data()
    qty = data.get("items", {}).get(name, {}).get("sizes", {}).get(size, 0)

    if qty <= 0:
        await callback.answer("Уже 0", show_alert=True)
        return

    await callback.message.edit_text(
        f"<b>{name}</b>\nРазмер: <b>{size}</b>\nСейчас: <b>{qty}</b> шт\n\n"
        f"На сколько уменьшить?",
        reply_markup=amount_kb(name, size, qty),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.callback_query(F.data.startswith("do_dec:"))
async def do_decrease(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    _, name, size, amount = callback.data.split(":")
    amount = int(amount)

    data = load_data()
    items = data.get("items", {})
    if name not in items or size not in items[name]["sizes"]:
        await callback.answer("Ошибка", show_alert=True)
        return

    current = items[name]["sizes"][size]
    new_qty = max(0, current - amount)
    items[name]["sizes"][size] = new_qty
    save_data(data)

    await callback.message.edit_text(
        f"✅ Списано {amount} шт\n\n"
        f"<b>{name}</b>\nРазмер {size}: было {current} → стало <b>{new_qty}</b>",
        reply_markup=item_actions_kb(name),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

# ---------- Удаление ----------
@router.callback_query(F.data.startswith("delete:"))
async def delete_item(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    name = callback.data.split(":", 1)[1]
    data = load_data()

    if name in data.get("items", {}):
        del data["items"][name]
        save_data(data)
        await callback.message.edit_text(
            f"🗑 Вещь <b>{name}</b> удалена.",
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("Уже удалена", show_alert=True)
    await callback.answer()

# ---------- Отмена ----------
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu_kb())

# ------------------ Запуск ------------------
async def main():
    dp.include_router(router)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
