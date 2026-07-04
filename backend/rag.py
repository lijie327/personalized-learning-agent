"""
教育知识库 RAG 模块
预设课程内容，支持向量化检索和混合检索。
"""

from typing import Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.llm import QwenEmbeddings

# ---------------------------------------------------------------------------
#  预设课程知识库
# ---------------------------------------------------------------------------

COURSE_DATA: Dict[str, Dict[str, str]] = {
    # ======================== Python 基础 ========================
    "python": {
        "变量": """
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
""",
        "函数": """
# Python 函数详解

函数是组织代码的基本单元，用于封装可复用的逻辑。

## 定义与调用
```python
def greet(name: str) -> str:
    \"\"\"向指定的人打招呼（这是文档字符串 docstring）。\"\"\"
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
    \"\"\"返回一个乘以 factor 的函数。\"\"\"
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
    \"\"\"测量函数执行时间的装饰器。\"\"\"
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
""",
        "类": """
# Python 面向对象 —— 类详解

类是面向对象编程的核心，用于将数据和行为封装在一起。

## 基本定义
```python
class Student:
    \"\"\"学生类，记录学生的基本信息。\"\"\"

    # 类变量 —— 所有实例共享
    school = "阳光中学"
    student_count = 0

    def __init__(self, name: str, age: int, grade: float):
        \"\"\"构造方法，创建实例时自动调用。\"\"\"
        # 实例变量 —— 每个实例独有
        self.name = name
        self.age = age
        self.grade = grade
        Student.student_count += 1

    def introduce(self) -> str:
        \"\"\"实例方法：自我介绍。\"\"\"
        return f"我是{self.name}，{self.age}岁，成绩{self.grade}分。"

    @classmethod
    def get_school(cls) -> str:
        \"\"\"类方法：可以访问和修改类变量。\"\"\"
        return f"学校：{cls.school}，共{cls.student_count}名学生"

    @staticmethod
    def is_passing(grade: float) -> bool:
        \"\"\"静态方法：不需要 cls 或 self，相当于普通函数。\"\"\"
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
        \"\"\"用 @property 将方法变成只读属性。\"\"\"
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
        \"\"\"开发调试时的字符串表示。\"\"\"
        return f"Vector({self.x}, {self.y})"

    def __str__(self) -> str:
        \"\"\"用户友好的字符串表示。\"\"\"
        return f"({self.x}, {self.y})"

    def __add__(self, other):
        \"\"\"支持 + 运算符。\"\"\"
        return Vector(self.x + other.x, self.y + other.y)

    def __eq__(self, other):
        \"\"\"支持 == 运算符。\"\"\"
        return self.x == other.x and self.y == other.y

    def __len__(self):
        \"\"\"支持 len() —— 这里返回向量模长的整数部分。\"\"\"
        return int((self.x**2 + self.y**2)**0.5)

v1 = Vector(3, 4)
v2 = Vector(1, 2)
print(v1 + v2)   # (4, 6)
print(v1 == Vector(3, 4))  # True
```
""",
        "异常处理": """
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
    \"\"\"余额不足异常。\"\"\"
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
""",
    },
    # ======================== 数据结构 ========================
    "data_structures": {
        "数组": """
# 数组 (Array) —— 数据结构基础

数组是最基础的线性数据结构，在内存中连续存储元素，支持通过索引 O(1) 随机访问。

## 核心特性
- **连续内存**：元素在内存中紧密排列
- **随机访问**：通过下标直接定位，时间 O(1)
- **插入/删除慢**：中间位置需要移动元素，平均 O(n)
- **空间固定**（静态数组）或动态扩容（动态数组）

## Python 中的数组
Python 的 list 是动态数组，底层实现是 C 的指针数组。

```python
# 创建
arr = [10, 20, 30, 40, 50]

# 访问 —— O(1)
print(arr[2])   # 30
print(arr[-1])  # 50（负索引从尾部算）

# 追加 —— 均摊 O(1)
arr.append(60)

# 插入 —— O(n)，需要移动后面的元素
arr.insert(0, 5)  # 在头部插入

# 删除 —— O(n)
arr.pop()       # 删除尾部，O(1)
arr.pop(0)      # 删除头部，O(n)
arr.remove(30)  # 按值删除，O(n)
```

## 经典算法应用

### 二分查找（要求数组有序）
```python
def binary_search(arr, target):
    \"\"\"在有序数组中查找目标值，返回索引，未找到返回 -1。\"\"\"
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# 时间复杂度：O(log n)
```

### 双指针技巧
```python
def two_sum_sorted(arr, target):
    \"\"\"在有序数组中找两个数之和等于 target。\"\"\"
    left, right = 0, len(arr) - 1
    while left < right:
        s = arr[left] + arr[right]
        if s == target:
            return [left, right]
        elif s < target:
            left += 1
        else:
            right -= 1
    return []
```

### 滑动窗口
```python
def max_subarray_sum(arr, k):
    \"\"\"长度为 k 的连续子数组的最大和。\"\"\"
    window_sum = sum(arr[:k])
    max_sum = window_sum
    for i in range(k, len(arr)):
        window_sum += arr[i] - arr[i - k]
        max_sum = max(max_sum, window_sum)
    return max_sum
```

## 复杂度总结
| 操作 | 时间复杂度 |
|------|-----------|
| 随机访问 | O(1) |
| 尾部追加 | O(1) 均摊 |
| 头部插入 | O(n) |
| 中间插入 | O(n) |
| 查找（无序）| O(n) |
| 查找（有序，二分）| O(log n) |
""",
        "链表": """
# 链表 (Linked List) —— 数据结构基础

链表通过指针将分散在内存中的节点串联起来，支持 O(1) 的头部插入/删除。

## 核心特性
- **非连续存储**：每个节点包含数据和指向下一节点的指针
- **动态大小**：不需要预先分配空间
- **插入/删除快**：已知位置时 O(1)
- **随机访问慢**：需要从头遍历，O(n)

## 单链表实现
```python
class ListNode:
    \"\"\"链表节点。\"\"\"
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class LinkedList:
    def __init__(self):
        self.head = None  # 哨兵头节点（dummy）简化边界处理
        self.size = 0

    def get(self, index: int) -> int:
        \"\"\"获取第 index 个节点的值。\"\"\"
        if index < 0 or index >= self.size:
            return -1
        curr = self.head
        for _ in range(index):
            curr = curr.next
        return curr.val

    def add_at_head(self, val: int):
        \"\"\"在头部插入。\"\"\"
        new_node = ListNode(val, self.head)
        self.head = new_node
        self.size += 1

    def add_at_tail(self, val: int):
        \"\"\"在尾部插入。\"\"\"
        if not self.head:
            self.head = ListNode(val)
        else:
            curr = self.head
            while curr.next:
                curr = curr.next
            curr.next = ListNode(val)
        self.size += 1

    def delete_at_index(self, index: int):
        \"\"\"删除第 index 个节点。\"\"\"
        if index < 0 or index >= self.size:
            return
        if index == 0:
            self.head = self.head.next
        else:
            curr = self.head
            for _ in range(index - 1):
                curr = curr.next
            curr.next = curr.next.next
        self.size -= 1
```

## 经典题目

### 反转链表
```python
def reverse_list(head):
    \"\"\"迭代法反转链表。\"\"\"
    prev, curr = None, head
    while curr:
        nxt = curr.next    # 先保存下一个节点
        curr.next = prev   # 反转指针
        prev = curr        # prev 前进一步
        curr = nxt         # curr 前进一步
    return prev
# 时间 O(n)，空间 O(1)
```

### 检测环
```python
def has_cycle(head):
    \"\"\"快慢指针法（Floyd 判圈算法）。\"\"\"
    slow = fast = head
    while fast and fast.next:
        slow = slow.next       # 每次走一步
        fast = fast.next.next  # 每次走两步
        if slow == fast:
            return True
    return False
# 时间 O(n)，空间 O(1)
```

### 合并两个有序链表
```python
def merge_two_lists(l1, l2):
    dummy = ListNode(0)
    curr = dummy
    while l1 and l2:
        if l1.val <= l2.val:
            curr.next = l1
            l1 = l1.next
        else:
            curr.next = l2
            l2 = l2.next
        curr = curr.next
    curr.next = l1 or l2
    return dummy.next
```

## 链表 vs 数组
| 特性 | 数组 | 链表 |
|------|------|------|
| 内存 | 连续 | 分散 |
| 随机访问 | O(1) | O(n) |
| 头部插入 | O(n) | O(1) |
| 尾部插入 | O(1) | O(n)（无尾指针）/ O(1)（有尾指针）|
| 缓存友好 | 是 | 否 |
""",
        "栈": """
# 栈 (Stack) —— 数据结构基础

栈是一种后进先出 (LIFO, Last In First Out) 的线性数据结构。

## 核心特性
- **LIFO 原则**：最后压入的元素最先弹出
- **只操作一端**：栈顶（top）
- **基本操作**：push（入栈）、pop（出栈）、peek/top（查看栈顶）
- **所有操作 O(1)**

## Python 实现
```python
# 方式一：使用 list（推荐，C 实现速度快）
stack = []
stack.append(1)   # push
stack.append(2)
stack.append(3)
print(stack[-1])  # peek → 3
stack.pop()       # pop → 3
print(stack)      # [1, 2]

# 方式二：使用 collections.deque（线程安全，两端操作 O(1)）
from collections import deque
stack = deque()
stack.append(1)
stack.append(2)
stack.pop()
```

## 封装为类
```python
class Stack:
    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("栈为空")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("栈为空")
        return self._items[-1]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def size(self) -> int:
        return len(self._items)
```

## 经典应用

### 1. 括号匹配
```python
def is_valid(s: str) -> bool:
    \"\"\"判断括号字符串是否合法配对。\"\"\"
    mapping = {')': '(', ']': '[', '}': '{'}
    stack = []
    for char in s:
        if char in mapping:          # 右括号
            top = stack.pop() if stack else '#'
            if mapping[char] != top:
                return False
        else:                         # 左括号
            stack.append(char)
    return len(stack) == 0

# is_valid("()[]{}") → True
# is_valid("([)]")   → False
```

### 2. 最小栈
```python
class MinStack:
    \"\"\"支持 O(1) 获取最小值的栈。\"\"\"
    def __init__(self):
        self.stack = []
        self.min_stack = []  # 辅助栈，记录每个位置的最小值

    def push(self, val):
        self.stack.append(val)
        if not self.min_stack:
            self.min_stack.append(val)
        else:
            self.min_stack.append(min(val, self.min_stack[-1]))

    def pop(self):
        self.stack.pop()
        self.min_stack.pop()

    def get_min(self):
        return self.min_stack[-1]
```

### 3. 表达式求值（逆波兰表达式）
```python
def eval_rpn(tokens):
    \"\"\"计算逆波兰表达式。\"\"\"
    stack = []
    operators = {'+', '-', '*', '/'}
    for token in tokens:
        if token not in operators:
            stack.append(int(token))
        else:
            b = stack.pop()
            a = stack.pop()
            if token == '+': stack.append(a + b)
            elif token == '-': stack.append(a - b)
            elif token == '*': stack.append(a * b)
            elif token == '/': stack.append(int(a / b))  # 向零取整
    return stack[0]

# eval_rpn(["2","1","+","3","*"]) → 9  即 (2+1)*3
```
""",
        "队列": """
# 队列 (Queue) —— 数据结构基础

队列是一种先进先出 (FIFO, First In First Out) 的线性数据结构。

## 核心特性
- **FIFO 原则**：最先入队的元素最先出队
- **两端操作**：队尾入队（enqueue），队头出队（dequeue）
- **基本操作 O(1)**

## Python 实现
```python
from collections import deque

# 推荐使用 deque（双端队列），两端操作都是 O(1)
queue = deque()
queue.append(1)     # 入队
queue.append(2)
queue.append(3)
print(queue[0])     # 查看队头 → 1
queue.popleft()     # 出队 → 1
print(queue)        # deque([2, 3])

# 注意：不要用 list 做队列！
# list.pop(0) 是 O(n)，deque.popleft() 是 O(1)
```

## 封装为类
```python
class Queue:
    def __init__(self):
        self._items = deque()

    def enqueue(self, item):
        \"\"\"入队：添加到队尾。\"\"\"
        self._items.append(item)

    def dequeue(self):
        \"\"\"出队：从队头移除并返回。\"\"\"
        if self.is_empty():
            raise IndexError("队列为空")
        return self._items.popleft()

    def front(self):
        \"\"\"查看队头元素。\"\"\"
        if self.is_empty():
            raise IndexError("队列为空")
        return self._items[0]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def size(self) -> int:
        return len(self._items)
```

## 特殊队列变体

### 双端队列 (Deque)
```python
from collections import deque
dq = deque([1, 2, 3])
dq.appendleft(0)    # 左端添加 → deque([0, 1, 2, 3])
dq.append(4)        # 右端添加 → deque([0, 1, 2, 3, 4])
dq.popleft()        # 左端弹出 → 0
dq.pop()            # 右端弹出 → 4
```

### 优先队列 (Priority Queue)
```python
import heapq

# 最小堆实现优先队列
pq = []
heapq.heappush(pq, (3, "任务C"))
heapq.heappush(pq, (1, "任务A"))
heapq.heappush(pq, (2, "任务B"))

# 按优先级（数值小的优先）弹出
print(heapq.heappop(pq))  # (1, '任务A')
print(heapq.heappop(pq))  # (2, '任务B')
```

## 经典应用

### BFS 广度优先搜索
```python
from collections import deque

def bfs(graph, start):
    \"\"\"图的广度优先遍历。\"\"\"
    visited = set([start])
    queue = deque([start])
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return result

# 示例
graph = {
    'A': ['B', 'C'],
    'B': ['D', 'E'],
    'C': ['F'],
    'D': [], 'E': [], 'F': []
}
print(bfs(graph, 'A'))  # ['A', 'B', 'C', 'D', 'E', 'F']
```

### 用两个栈实现队列
```python
class MyQueue:
    \"\"\"面试题经典：用两个栈模拟队列。\"\"\"
    def __init__(self):
        self.in_stack = []   # 入栈
        self.out_stack = []  # 出栈

    def push(self, x):
        self.in_stack.append(x)

    def pop(self):
        if not self.out_stack:
            while self.in_stack:
                self.out_stack.append(self.in_stack.pop())
        return self.out_stack.pop()

    def peek(self):
        if not self.out_stack:
            while self.in_stack:
                self.out_stack.append(self.in_stack.pop())
        return self.out_stack[-1]
```
""",
        "树": """
# 树 (Tree) —— 数据结构基础

树是一种非线性层次数据结构，由节点和边组成，具有递归性质。

## 基本术语
- **根节点 (Root)**：树的顶部节点
- **叶子节点 (Leaf)**：没有子节点的节点
- **深度 (Depth)**：从根到该节点的路径长度
- **高度 (Height)**：从该节点到最远叶子的路径长度
- **度 (Degree)**：节点的子节点个数

## 二叉树
```python
class TreeNode:
    \"\"\"二叉树节点。\"\"\"
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
```

### 三种遍历方式
```python
def preorder(root):
    \"\"\"前序遍历：根 → 左 → 右。\"\"\"
    if not root:
        return []
    return [root.val] + preorder(root.left) + preorder(root.right)

def inorder(root):
    \"\"\"中序遍历：左 → 根 → 右（BST 中序为有序序列）。\"\"\"
    if not root:
        return []
    return inorder(root.left) + [root.val] + inorder(root.right)

def postorder(root):
    \"\"\"后序遍历：左 → 右 → 根。\"\"\"
    if not root:
        return []
    return postorder(root.left) + postorder(root.right) + [root.val]
```

### 层序遍历 (BFS)
```python
from collections import deque

def level_order(root):
    \"\"\"按层输出二叉树。\"\"\"
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        level = []
        for _ in range(level_size):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    return result

# 示例树:      1
#            / \\
#           2   3
#          / \\
#         4   5
# level_order → [[1], [2, 3], [4, 5]]
```

## 二叉搜索树 (BST)
```python
class BST:
    \"\"\"二叉搜索树：左 < 根 < 右。\"\"\"
    def __init__(self):
        self.root = None

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, node, val):
        if not node:
            return TreeNode(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        else:
            node.right = self._insert(node.right, val)
        return node

    def search(self, val) -> bool:
        return self._search(self.root, val)

    def _search(self, node, val) -> bool:
        if not node:
            return False
        if val == node.val:
            return True
        elif val < node.val:
            return self._search(node.left, val)
        else:
            return self._search(node.right, val)
```

## 经典题目

### 最大深度
```python
def max_depth(root) -> int:
    if not root:
        return 0
    return 1 + max(max_depth(root.left), max_depth(root.right))
```

### 判断对称二叉树
```python
def is_symmetric(root) -> bool:
    def check(left, right):
        if not left and not right:
            return True
        if not left or not right:
            return False
        return (left.val == right.val
                and check(left.left, right.right)
                and check(left.right, right.left))  # 对称：左子树的右 vs 右子树的左
    return check(root.left, root.right) if root else True
```

## 树的复杂度
| 操作 | 平均 | 最坏（退化为链表）|
|------|------|----------------|
| 查找 | O(log n) | O(n) |
| 插入 | O(log n) | O(n) |
| 删除 | O(log n) | O(n) |

平衡树（AVL / 红黑树）可以保证 O(log n) 的最坏情况。
""",
    },
}


class EducationKnowledgeBase:
    """
    教育知识库：管理课程内容的向量化存储与检索。

    使用 RecursiveCharacterTextSplitter 对课程文本进行分块，
    通过 QwenEmbeddings 向量化后存入 ChromaDB。
    """

    def __init__(self, persist_directory: str = "./chroma_db"):
        import os

        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)

        self.embeddings = QwenEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            separators=["\n## ", "\n### ", "\n```", "\n\n", "\n", " ", ""],
        )

        # 存储已初始化的科目集合
        self._initialized_subjects: set = set()

        # 原始课程数据引用（供 get_learning_materials 使用）
        self._raw_data = COURSE_DATA

        # 持久化 ChromaDB 客户端（在 _get_or_create_collection 中懒加载）
        self._client = None
        self._collections: Dict[str, object] = {}

    # ------------------------------------------------------------------
    #  初始化 & 建库
    # ------------------------------------------------------------------

    def _get_or_create_collection(self, subject: str):
        """获取或创建指定科目的 ChromaDB 集合（持久化存储）。"""
        import chromadb

        if subject not in self._collections:
            # 懒加载：首次使用时创建持久化客户端
            if self._client is None:
                self._client = chromadb.PersistentClient(path=self.persist_directory)

            collection = self._client.get_or_create_collection(
                name=f"edu_{subject}",
                metadata={"subject": subject},
            )
            self._collections[subject] = collection

            # 如果该科目尚未入库，执行向量化写入
            if subject not in self._initialized_subjects:
                self._ingest_subject(subject, collection)
                self._initialized_subjects.add(subject)

        return self._collections[subject]

    def _ingest_subject(self, subject: str, collection):
        """将指定科目的所有课程文本分块、向量化后写入 ChromaDB。"""
        topics = self._raw_data.get(subject, {})
        if not topics:
            return

        all_chunks = []
        all_ids = []
        all_metadatas = []

        for topic, content in topics.items():
            chunks = self.text_splitter.split_text(content)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                chunk_id = f"{subject}_{topic}_chunk_{i}"
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "subject": subject,
                    "topic": topic,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })

        if not all_chunks:
            return

        # 向量化
        vectors = self.embeddings.embed_documents(all_chunks)

        # 写入 ChromaDB
        collection.add(
            documents=all_chunks,
            embeddings=vectors,
            metadatas=all_metadatas,
            ids=all_ids,
        )

    # ------------------------------------------------------------------
    #  检索方法
    # ------------------------------------------------------------------

    def search(self, query: str, subject: str, k: int = 3) -> List[dict]:
        """
        按科目进行向量检索。

        Args:
            query: 检索查询文本。
            subject: 科目名称（如 'python' / 'data_structures'）。
            k: 返回结果数量。

        Returns:
            列表，每项包含 content / topic / score 等字段。
        """
        collection = self._get_or_create_collection(subject)

        # 检查集合是否有文档
        if collection.count() == 0:
            return []

        query_embedding = self.embeddings.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, collection.count()),
            where={"subject": subject},
        )

        # 整理返回结果
        items = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append({
                    "content": doc,
                    "topic": meta.get("topic", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": 1.0 - dist,  # ChromaDB 返回 L2 距离，转为相似度
                })

        return items

    def hybrid_search(self, query: str, subject: str, k: int = 5) -> List[dict]:
        """
        混合检索：向量检索 + 关键词重排序。

        先通过向量检索召回候选结果，再使用关键词匹配对结果进行重排序，
        提升与查询关键词直接相关的文档排名。

        Args:
            query: 检索查询文本。
            subject: 科目名称。
            k: 最终返回结果数量。

        Returns:
            重排序后的结果列表。
        """
        # 第一步：向量检索召回更多候选
        candidates = self.search(query, subject, k=k * 3)

        if not candidates:
            return []

        # 第二步：关键词提取与重排序
        query_keywords = self._extract_keywords(query)

        for item in candidates:
            content_lower = item["content"].lower()
            keyword_score = sum(
                1 for kw in query_keywords if kw.lower() in content_lower
            )
            # 混合分数 = 0.7 * 向量相似度 + 0.3 * 关键词命中率
            keyword_norm = keyword_score / max(len(query_keywords), 1)
            item["hybrid_score"] = 0.7 * item["score"] + 0.3 * keyword_norm

        # 按混合分数降序排序
        candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return candidates[:k]

    def get_learning_materials(
        self, subject: str, topic: str
    ) -> List[dict]:
        """
        获取指定科目和主题的完整学习材料。

        Args:
            subject: 科目名称（如 'python'）。
            topic: 主题名称（如 '变量'）。

        Returns:
            该主题所有分块的列表，按顺序排列。
        """
        subject_data = self._raw_data.get(subject, {})
        content = subject_data.get(topic, "")

        if not content:
            return []

        chunks = self.text_splitter.split_text(content)
        return [
            {
                "content": chunk,
                "subject": subject,
                "topic": topic,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i, chunk in enumerate(chunks)
        ]

    def list_subjects(self) -> List[str]:
        """列出所有可用科目。"""
        return list(self._raw_data.keys())

    def list_topics(self, subject: str) -> List[str]:
        """列出指定科目的所有主题。"""
        return list(self._raw_data.get(subject, {}).keys())

    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """
        简易关键词提取：按空格和标点分词，过滤短词。

        实际生产环境可替换为 jieba 分词或 BGE Reranker。
        """
        import re
        # 中文按连续字符切分，英文按单词切分
        tokens = re.findall(r"[一-鿿]+|[a-zA-Z_]\w*", text)
        # 过滤长度小于 2 的词
        return [t for t in tokens if len(t) >= 2]
