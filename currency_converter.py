import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
from datetime import datetime
from threading import Thread

# -------------------------------------------------------------------
# НАСТРОЙКИ API (exchangerate-api.com)
# -------------------------------------------------------------------
# Бесплатный ключ можно получить на https://app.exchangerate-api.com/sign-up
API_KEY = "ваш_api_ключ"          # Замените на свой ключ
BASE_URL = "https://api.exchangerate-api.com/v4/latest/"

# -------------------------------------------------------------------
# КЛАСС ДЛЯ РАБОТЫ С ИСТОРИЕЙ (JSON)
# -------------------------------------------------------------------
class HistoryManager:
    def __init__(self, filename="history.json"):
        self.filename = filename
        self.history = self.load_history()

    def load_history(self):
        """Загружает историю из JSON-файла."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def save_history(self):
        """Сохраняет историю в JSON-файл."""
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def add_record(self, record):
        """Добавляет запись в историю и сохраняет."""
        self.history.append(record)
        self.save_history()

    def clear_history(self):
        """Очищает историю."""
        self.history = []
        self.save_history()

# -------------------------------------------------------------------
# ОСНОВНОЕ ПРИЛОЖЕНИЕ
# -------------------------------------------------------------------
class CurrencyConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Currency Converter")
        self.root.geometry("750x500")
        self.root.resizable(True, True)

        # Менеджер истории
        self.history_mgr = HistoryManager()

        # Доступные валюты (заполним позже из API)
        self.currencies = []
        self.exchange_rates = {}     # ключ: базовая валюта, значение: словарь курсов

        # Создание интерфейса
        self.create_widgets()

        # Загружаем список валют в фоновом потоке
        self.load_currencies_thread()

    # -----------------------------------------------------------------
    # ПОСТРОЕНИЕ GUI
    # -----------------------------------------------------------------
    def create_widgets(self):
        # Рамка для ввода и конвертации
        input_frame = ttk.LabelFrame(self.root, text="Конвертация", padding=10)
        input_frame.pack(fill="x", padx=10, pady=5)

        # Сумма
        ttk.Label(input_frame, text="Сумма:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(input_frame, textvariable=self.amount_var, width=15)
        self.amount_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Из валюты
        ttk.Label(input_frame, text="Из валюты:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.from_currency_var = tk.StringVar()
        self.from_combo = ttk.Combobox(input_frame, textvariable=self.from_currency_var, width=8)
        self.from_combo.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        # В валюту
        ttk.Label(input_frame, text="В валюту:").grid(row=0, column=4, sticky="w", padx=5, pady=5)
        self.to_currency_var = tk.StringVar()
        self.to_combo = ttk.Combobox(input_frame, textvariable=self.to_currency_var, width=8)
        self.to_combo.grid(row=0, column=5, sticky="w", padx=5, pady=5)

        # Кнопка конвертации
        self.convert_btn = ttk.Button(input_frame, text="Конвертировать", command=self.convert)
        self.convert_btn.grid(row=0, column=6, padx=10, pady=5)

        # Результат
        self.result_label = ttk.Label(input_frame, text="Результат: --", font=("Arial", 10, "bold"))
        self.result_label.grid(row=1, column=0, columnspan=7, sticky="w", padx=5, pady=5)

        # Таблица истории
        history_frame = ttk.LabelFrame(self.root, text="История конвертаций", padding=10)
        history_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Создаём Treeview с прокруткой
        columns = ("datetime", "from_currency", "from_amount", "to_currency", "to_amount", "rate")
        self.tree = ttk.Treeview(history_frame, columns=columns, show="headings")
        self.tree.heading("datetime", text="Дата/время")
        self.tree.heading("from_currency", text="Из")
        self.tree.heading("from_amount", text="Сумма")
        self.tree.heading("to_currency", text="В")
        self.tree.heading("to_amount", text="Результат")
        self.tree.heading("rate", text="Курс")
        self.tree.column("datetime", width=140)
        self.tree.column("from_currency", width=60)
        self.tree.column("from_amount", width=80)
        self.tree.column("to_currency", width=60)
        self.tree.column("to_amount", width=100)
        self.tree.column("rate", width=80)

        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Кнопка очистки истории
        clear_btn = ttk.Button(self.root, text="Очистить историю", command=self.clear_history)
        clear_btn.pack(pady=5)

        # Загружаем историю в таблицу
        self.refresh_history_table()

    # -----------------------------------------------------------------
    # РАБОТА С API
    # -----------------------------------------------------------------
    def load_currencies_thread(self):
        """Запускает загрузку списка валют в отдельном потоке."""
        self.convert_btn.config(state="disabled")
        self.status_label = ttk.Label(self.root, text="Загрузка курсов валют...", foreground="blue")
        self.status_label.pack(side="bottom", anchor="w", padx=10, pady=2)

        thread = Thread(target=self.fetch_currencies, daemon=True)
        thread.start()

    def fetch_currencies(self):
        """Получает список валют и базовые курсы (относительно USD)."""
        try:
            # Для получения списка всех валют используем базовую USD
            url = BASE_URL + "USD"
            if API_KEY != "ваш_api_ключ":
                url += f"?api_key={API_KEY}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Курсы относительно USD
            self.exchange_rates = data.get("rates", {})
            self.currencies = sorted(self.exchange_rates.keys())

            # Обновляем комбобоксы в основном потоке
            self.root.after(0, self.update_currency_lists)
            self.root.after(0, lambda: self.status_label.destroy())
            self.root.after(0, lambda: self.convert_btn.config(state="normal"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка API", f"Не удалось загрузить курсы:\n{e}"))
            self.root.after(0, lambda: self.status_label.destroy())
            self.root.after(0, lambda: self.convert_btn.config(state="normal"))

    def update_currency_lists(self):
        """Заполняет выпадающие списки доступными валютами."""
        self.from_combo['values'] = self.currencies
        self.to_combo['values'] = self.currencies
        if self.currencies:
            self.from_currency_var.set("USD")
            self.to_currency_var.set("EUR")

    # -----------------------------------------------------------------
    # КОНВЕРТАЦИЯ
    # -----------------------------------------------------------------
    def convert(self):
        # Валидация суммы
        amount_str = self.amount_var.get().strip()
        if not amount_str:
            messagebox.showwarning("Некорректный ввод", "Введите сумму для конвертации.")
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except ValueError:
            messagebox.showwarning("Некорректный ввод", "Сумма должна быть положительным числом (например, 100.50).")
            return

        from_curr = self.from_currency_var.get()
        to_curr = self.to_currency_var.get()
        if not from_curr or not to_curr:
            messagebox.showwarning("Внимание", "Выберите обе валюты.")
            return

        # Проверяем, загружены ли курсы
        if not self.exchange_rates:
            messagebox.showerror("Ошибка", "Курсы валют ещё не загружены. Подождите или проверьте интернет.")
            return

        # Конвертация через USD как базовую
        try:
            # Если исходная валюта не USD, сначала переводим сумму в USD
            if from_curr == "USD":
                amount_in_usd = amount
            else:
                usd_rate = self.exchange_rates.get(from_curr)
                if not usd_rate:
                    raise KeyError(f"Нет курса для {from_curr}")
                amount_in_usd = amount / usd_rate

            # Из USD в целевую валюту
            if to_curr == "USD":
                result = amount_in_usd
            else:
                target_rate = self.exchange_rates.get(to_curr)
                if not target_rate:
                    raise KeyError(f"Нет курса для {to_curr}")
                result = amount_in_usd * target_rate

            # Округляем до 2 знаков (можно изменить)
            result = round(result, 2)
            rate_used = round(result / amount, 4) if amount != 0 else 0

            # Выводим результат
            self.result_label.config(text=f"Результат: {result} {to_curr}")

            # Сохраняем в историю
            record = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_currency": from_curr,
                "from_amount": amount,
                "to_currency": to_curr,
                "to_amount": result,
                "rate": rate_used
            }
            self.history_mgr.add_record(record)
            self.refresh_history_table()

        except KeyError as e:
            messagebox.showerror("Ошибка конвертации", f"Валюта не найдена: {e}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Что-то пошло не так:\n{e}")

    # -----------------------------------------------------------------
    # РАБОТА С ИСТОРИЕЙ (ТАБЛИЦА)
    # -----------------------------------------------------------------
    def refresh_history_table(self):
        """Очищает таблицу и заново заполняет её из history_mgr."""
        for row in self.tree.get_children():
            self.tree.delete(row)

        for record in reversed(self.history_mgr.history):  # новые сверху
            self.tree.insert("", "end", values=(
                record["datetime"],
                record["from_currency"],
                record["from_amount"],
                record["to_currency"],
                record["to_amount"],
                record["rate"]
            ))

    def clear_history(self):
        """Очищает историю (с подтверждением)."""
        if messagebox.askyesno("Очистка истории", "Вы уверены, что хотите удалить всю историю?"):
            self.history_mgr.clear_history()
            self.refresh_history_table()
            messagebox.showinfo("Готово", "История очищена.")

# -------------------------------------------------------------------
# ЗАПУСК ПРИЛОЖЕНИЯ
# -------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = CurrencyConverterApp(root)
    root.mainloop()