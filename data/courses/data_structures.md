#TOPIC: 数组

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
    """在有序数组中查找目标值，返回索引，未找到返回 -1。"""
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
    """在有序数组中找两个数之和等于 target。"""
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
    """长度为 k 的连续子数组的最大和。"""
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

#TOPIC: 链表

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
    """链表节点。"""
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class LinkedList:
    def __init__(self):
        self.head = None  # 哨兵头节点（dummy）简化边界处理
        self.size = 0

    def get(self, index: int) -> int:
        """获取第 index 个节点的值。"""
        if index < 0 or index >= self.size:
            return -1
        curr = self.head
        for _ in range(index):
            curr = curr.next
        return curr.val

    def add_at_head(self, val: int):
        """在头部插入。"""
        new_node = ListNode(val, self.head)
        self.head = new_node
        self.size += 1

    def add_at_tail(self, val: int):
        """在尾部插入。"""
        if not self.head:
            self.head = ListNode(val)
        else:
            curr = self.head
            while curr.next:
                curr = curr.next
            curr.next = ListNode(val)
        self.size += 1

    def delete_at_index(self, index: int):
        """删除第 index 个节点。"""
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
    """迭代法反转链表。"""
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
    """快慢指针法（Floyd 判圈算法）。"""
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

#TOPIC: 栈

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
    """判断括号字符串是否合法配对。"""
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
    """支持 O(1) 获取最小值的栈。"""
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
    """计算逆波兰表达式。"""
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

#TOPIC: 队列

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
        """入队：添加到队尾。"""
        self._items.append(item)

    def dequeue(self):
        """出队：从队头移除并返回。"""
        if self.is_empty():
            raise IndexError("队列为空")
        return self._items.popleft()

    def front(self):
        """查看队头元素。"""
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
    """图的广度优先遍历。"""
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
    """面试题经典：用两个栈模拟队列。"""
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

#TOPIC: 树

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
    """二叉树节点。"""
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
```

### 三种遍历方式
```python
def preorder(root):
    """前序遍历：根 → 左 → 右。"""
    if not root:
        return []
    return [root.val] + preorder(root.left) + preorder(root.right)

def inorder(root):
    """中序遍历：左 → 根 → 右（BST 中序为有序序列）。"""
    if not root:
        return []
    return inorder(root.left) + [root.val] + inorder(root.right)

def postorder(root):
    """后序遍历：左 → 右 → 根。"""
    if not root:
        return []
    return postorder(root.left) + postorder(root.right) + [root.val]
```

### 层序遍历 (BFS)
```python
from collections import deque

def level_order(root):
    """按层输出二叉树。"""
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
#            / \
#           2   3
#          / \
#         4   5
# level_order → [[1], [2, 3], [4, 5]]
```

## 二叉搜索树 (BST)
```python
class BST:
    """二叉搜索树：左 < 根 < 右。"""
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
