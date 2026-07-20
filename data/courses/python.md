#TOPIC: 变量

# Python 变量与数据类型

Python 是动态类型语言，变量不需要预先声明类型，赋值即创建。

## 基本规则
- 变量名必须以字母或下划线开头，不能以数字开头
- 变量名区分大小写（name 和 Name 是不同的变量）
- 遵循 PEP 8 命名规范：变量使用 snake_case 风格

## 基本数据类型
```python
# 整数 (int)
age = 25
negative_num = -10

# 浮点数 (float)
price = 19.99
pi = 3.14159

# 字符串 (str)
name = "Alice"
greeting = '你好世界'

# 布尔值 (bool)
is_active = True
is_empty = False

# None 类型
result = None
```

## 类型转换
```python
# 显式类型转换
num_str = "42"
num_int = int(num_str)      # 字符串转整数
num_float = float(num_str)  # 字符串转浮点数
back_str = str(num_int)     # 整数转字符串

# 注意：无法转换时会抛出 ValueError
# int("hello")  # 这会报错
```

## 多重赋值
```python
# 同时给多个变量赋值
x, y, z = 1, 2, 3

# 交换两个变量的值（Python 特有的优雅写法）
a, b = 10, 20
a, b = b, a  # 现在 a=20, b=10
```

## 变量引用机制
Python 中变量是对象的引用（标签），不是存储值的盒子：
```python
a = [1, 2, 3]
b = a        # b 和 a 指向同一个列表对象
b.append(4)
print(a)     # 输出 [1, 2, 3, 4]，a 也被修改了！

# 使用 id() 可以查看对象的内存地址
print(id(a) == id(b))  # True
```

#TOPIC: 函数

# Python 函数详解

函数是组织代码的基本单元，用于封装可复用的逻辑。

## 定义与调用
```python
def greet(name: str) -> str:
    """向指定的人打招呼（这是文档字符串 docstring）。"""
    return f"你好，{name}！"

# 调用函数
message = greet("小明")
print(message)  # 输出：你好，小明！
```

## 参数类型
```python
# 1. 位置参数 —— 按顺序传入
def power(base, exp):
    return base ** exp
power(2, 3)  # 8

# 2. 默认参数 —— 注意：默认值必须是不可变对象
def connect(host, port=3306, timeout=30):
    print(f"连接 {host}:{port}，超时 {timeout}s")
connect("localhost")          # 使用默认值
connect("db.server", 5432)    # 覆盖 port

# 3. 关键字参数 —— 调用时显式指定参数名
connect("localhost", timeout=5, port=3306)

# 4. *args —— 接收任意数量的位置参数，打包为元组
def total(*numbers):
    return sum(numbers)
total(1, 2, 3, 4)  # 10

# 5. **kwargs —— 接收任意数量的关键字参数，打包为字典
def show_info(**kwargs):
    for key, value in kwargs.items():
        print(f"{key}: {value}")
show_info(name="Alice", age=25, city="北京")
```

## 返回值
```python
# 返回多个值（实际是返回一个元组）
def min_max(numbers):
    return min(numbers), max(numbers)

lo, hi = min_max([3, 1, 4, 1, 5, 9])
# lo = 1, hi = 9

# 没有 return 或 return 后无表达式，返回 None
def do_nothing():
    pass
result = do_nothing()  # result 为 None
```

## Lambda 匿名函数
```python
# 适合简短的一次性函数
square = lambda x: x ** 2
add = lambda a, b: a + b

# 常与 sorted / map / filter 搭配
students = [("Alice", 85), ("Bob", 92), ("Charlie", 78)]
students.sort(key=lambda s: s[1], reverse=True)
# 按成绩降序排列
```

## 闭包 (Closure)
```python
def make_multiplier(factor):
    """返回一个乘以 factor 的函数。"""
    def multiplier(x):
        return x * factor  # factor 是外部函数的局部变量
    return multiplier

double = make_multiplier(2)
triple = make_multiplier(3)
print(double(5))   # 10
print(triple(5))   # 15
```

## 装饰器 (Decorator)
```python
import time

def timer(func):
    """测量函数执行时间的装饰器。"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__} 耗时 {elapsed:.4f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "完成"
```

#TOPIC: 类

# Python 面向对象 —— 类详解

类是面向对象编程的核心，用于将数据和行为封装在一起。

## 基本定义
```python
class Student:
    """学生类，记录学生的基本信息。"""

    # 类变量 —— 所有实例共享
    school = "阳光中学"
    student_count = 0

    def __init__(self, name: str, age: int, grade: float):
        """构造方法，创建实例时自动调用。"""
        # 实例变量 —— 每个实例独有
        self.name = name
        self.age = age
        self.grade = grade
        Student.student_count += 1

    def introduce(self) -> str:
        """实例方法：自我介绍。"""
        return f"我是{self.name}，{self.age}岁，成绩{self.grade}分。"

    @classmethod
    def get_school(cls) -> str:
        """类方法：可以访问和修改类变量。"""
        return f"学校：{cls.school}，共{cls.student_count}名学生"

    @staticmethod
    def is_passing(grade: float) -> bool:
        """静态方法：不需要 cls 或 self，相当于普通函数。"""
        return grade >= 60
```

## 继承
```python
class Animal:
    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:
        raise NotImplementedError("子类必须实现 speak 方法")

class Dog(Animal):
    def speak(self) -> str:
        return f"{self.name}：汪汪！"

class Cat(Animal):
    def speak(self) -> str:
        return f"{self.name}：喵~"

# 多态
animals = [Dog("旺财"), Cat("咪咪"), Dog("大黄")]
for animal in animals:
    print(animal.speak())

# 使用 super() 调用父类方法
class GuideDog(Dog):
    def __init__(self, name: str, owner: str):
        super().__init__(name)  # 调用父类构造
        self.owner = owner
```

## 属性封装
```python
class BankAccount:
    def __init__(self, owner: str, balance: float = 0):
        self.owner = owner         # 公开属性
        self._balance = balance    # 约定私有（_前缀）
        self.__pin = "1234"       # 名称改写（__前缀）

    @property
    def balance(self) -> float:
        """用 @property 将方法变成只读属性。"""
        return self._balance

    @balance.setter
    def balance(self, amount: float):
        if amount < 0:
            raise ValueError("余额不能为负数")
        self._balance = amount

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("存款金额必须大于0")
        self._balance += amount

account = BankAccount("Alice", 1000)
print(account.balance)       # 1000（通过 property 访问）
account.balance = 2000       # 通过 setter 修改
# account.balance = -100     # 抛出 ValueError
```

## 魔术方法（双下划线方法）
```python
class Vector:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        """开发调试时的字符串表示。"""
        return f"Vector({self.x}, {self.y})"

    def __str__(self) -> str:
        """用户友好的字符串表示。"""
        return f"({self.x}, {self.y})"

    def __add__(self, other):
        """支持 + 运算符。"""
        return Vector(self.x + other.x, self.y + other.y)

    def __eq__(self, other):
        """支持 == 运算符。"""
        return self.x == other.x and self.y == other.y

    def __len__(self):
        """支持 len() —— 这里返回向量模长的整数部分。"""
        return int((self.x**2 + self.y**2)**0.5)

v1 = Vector(3, 4)
v2 = Vector(1, 2)
print(v1 + v2)   # (4, 6)
print(v1 == Vector(3, 4))  # True
```

#TOPIC: 异常处理

# Python 异常处理

异常处理让程序能够优雅地应对错误，而不是直接崩溃。

## 基本语法
```python
try:
    # 可能出错的代码
    result = 10 / 0
except ZeroDivisionError:
    # 捕获特定异常
    print("除零错误！")
except (TypeError, ValueError) as e:
    # 同时捕获多种异常
    print(f"类型或值错误：{e}")
except Exception as e:
    # 捕获所有常规异常（兜底）
    print(f"未知错误：{e}")
else:
    # 没有异常时执行
    print(f"结果是：{result}")
finally:
    # 无论是否异常都会执行（常用于清理资源）
    print("清理完成")
```

## 常见内置异常
| 异常类型 | 触发场景 |
|---------|---------|
| ValueError | 值不合法，如 int("abc") |
| TypeError | 类型不匹配，如 "2" + 2 |
| KeyError | 字典键不存在 |
| IndexError | 列表索引越界 |
| FileNotFoundError | 文件不存在 |
| AttributeError | 对象没有该属性 |
| ZeroDivisionError | 除以零 |
| ImportError | 导入模块失败 |

## 自定义异常
```python
class InsufficientFundsError(Exception):
    """余额不足异常。"""
    def __init__(self, balance: float, amount: float):
        self.balance = balance
        self.amount = amount
        super().__init__(
            f"余额不足：当前余额 {balance} 元，需要 {amount} 元"
        )

class BankAccount:
    def __init__(self, balance: float = 0):
        self.balance = balance

    def withdraw(self, amount: float):
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount)
        self.balance -= amount

# 使用
account = BankAccount(100)
try:
    account.withdraw(200)
except InsufficientFundsError as e:
    print(e)  # 余额不足：当前余额 100 元，需要 200 元
    print(f"差额：{e.amount - e.balance} 元")
```

## 异常链 (Exception Chaining)
```python
# 使用 raise ... from ... 保留原始异常信息
def fetch_user_data(user_id: int) -> dict:
    try:
        response = api.get(f"/users/{user_id}")
        return response.json()
except ConnectionError as e:
    raise RuntimeError(f"获取用户 {user_id} 数据失败") from e
```

## 最佳实践
1. 只捕获你能处理的异常，不要裸 except
2. 用 finally 或 with 确保资源释放
3. 自定义异常继承自合适的内置异常
4. 用 raise ... from 保留异常链便于调试
5. 避免用异常做流程控制（性能差且不清晰）
