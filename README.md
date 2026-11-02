# 招聘大数据可视化分析平台

具有三种角色的登录模块，实现基于角色的访问控制。
## 功能特性   

### 用户角色

- **普通访客**：只能查看图表
- **VIP用户**：可以查看图表和数据，有筛选功能
- **管理员**：可以管理用户、爬虫、数据库

### 主要功能

- 用户注册、登录、密码重置
- 基于角色的访问控制
- JWT令牌认证
- 响应式前端界面
- 数据可视化图表
- 岗位筛选功能
- 用户管理后台
- 爬虫管理
- 数据库管理

## 技术栈

- **后端**：Flask, Python
- **前端**：React, React Router
- **数据库**：MySQL
- **认证**：JWT, bcrypt

## 项目结构

```
recruitment-platform/
├── backend/                    # 后端代码
│   ├── api/v1/                # API路由（版本化）
│   │   ├── auth.py           # 认证路由
│   │   ├── admin.py          # 管理员路由
│   │   └── data.py           # 数据路由
│   ├── core/                  # 核心模块
│   │   ├── config.py         # 配置文件
│   │   ├── init_db.py        # 数据库初始化
│   │   └── optimize_db.py    # 数据库优化
│   ├── models/                # 数据模型
│   │   ├── user.py           # 用户模型
│   │   └── role.py           # 角色模型
│   ├── utils/                 # 工具函数
│   │   ├── security.py       # 安全工具（密码哈希、JWT）
│   │   └── database.py       # 数据库连接工具
│   ├── middleware/            # 中间件
│   │   └── auth.py           # JWT认证中间件
│   ├── tests/                 # 单元测试
│   └── main.py               # 主应用入口
│
├── frontend/                  # 前端代码（React）
│   ├── public/                # 静态资源
│   │   └── index.html        # HTML入口
│   ├── src/                   # 源代码
│   │   ├── components/       # 组件
│   │   │   ├── Admin/        # 管理后台组件
│   │   │   ├── Auth/         # 认证组件
│   │   │   ├── Charts/       # 图表组件
│   │   │   ├── Data/         # 数据页组件
│   │   │   ├── Filter/       # 筛选组件
│   │   │   └── Layout/       # 布局组件
│   │   ├── utils/            # 工具函数
│   │   ├── App.js            # 主应用组件
│   │   └── index.js          # 入口文件
│   ├── package.json          # 依赖配置
│   ├── .eslintrc.json        # ESLint配置
│   └── .prettierrc           # Prettier配置
│
├── pcwjj/                     # 爬虫模块
│   ├── normalized_db.py      # 数据归一化入库
│   ├── resync_all.py         # 全量数据重同步
│   ├── qcwypc/               # 前程无忧爬虫
│   │   └── yingjie_spider/
│   │       └── crawler_pw.py # 应届生招聘 Playwright 爬虫
│   └── zlzppc/               # 智联招聘爬虫
│       └── crawler_pw.py     # 智联招聘 Playwright 爬虫
│
├── fix_data.py                # 数据修复脚本
├── .env                       # 环境变量
├── .env.example               # 环境变量示例
├── .gitignore                 # Git忽略文件
├── requirements.txt           # Python依赖
└── README.md                  # 项目说明
```

## 安装和运行

### 1. 安装后端依赖

```bash
pip install -r requirements.txt
# 爬虫模块基于 Playwright，需额外安装浏览器内核
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库等信息
```

### 3. 初始化数据库

```bash
cd backend
python core/init_db.py
```

### 4. 启动后端服务

```bash
cd backend
python main.py
```

### 5. 安装前端依赖

```bash
cd frontend
npm install
```

### 6. 启动前端服务

```bash
cd frontend
npm start
```

## 默认账户

系统初始化时会自动创建内置角色和权限。管理员账号需通过注册接口创建后，在数据库中手动分配 admin 角色，或使用数据库初始化脚本预置。

> ⚠️ **安全提示：** 生产环境务必通过环境变量设置强密码（DB_PASSWORD、JWT_SECRET），详见 `.env.example`。

## API文档

### 认证API

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/reset-password` - 密码重置
- `GET /api/auth/profile` - 获取用户信息
- `PUT /api/auth/update-profile` - 更新用户信息
- `PUT /api/auth/change-password` - 修改密码
- `POST /api/auth/apply-vip` - 申请 VIP

### 管理员API

- `GET /api/admin/users` - 获取用户列表
- `POST /api/admin/users` - 新增用户
- `DELETE /api/admin/users/<id>` - 删除用户
- `PUT /api/admin/users/<id>/role` - 修改用户角色
- `PUT /api/admin/users/<id>/status` - 启用/禁用用户
- `PUT /api/admin/users/<id>/reset-password` - 重置用户密码
- `GET /api/admin/permissions` - 获取权限列表
- `GET /api/admin/roles` - 获取角色列表
- `PUT /api/admin/roles/<id>/permissions` - 修改角色权限
- `GET /api/admin/vip-applications` - 获取 VIP 申请列表
- `POST /api/admin/vip-applications/<id>/approve` - 审批通过 VIP 申请
- `POST /api/admin/vip-applications/<id>/reject` - 驳回 VIP 申请
- `GET /api/admin/users/<id>/logs` - 查看用户活动日志

### 数据API

- `GET /api/v2/analysis` - 获取分析数据
- `GET /api/v2/data` - 获取数据
- `POST /api/v2/filter` - 筛选数据
- `GET /api/v2/filter/options` - 获取筛选选项
- `GET /api/job/page` - 分页查询岗位数据
- `GET /api/job/filter` - 筛选岗位数据
- `GET /api/job/detail` - 获取岗位详情
- `POST /api/job/favorite` - 收藏岗位
- `DELETE /api/job/favorite` - 取消收藏
- `GET /api/job/favorites` - 获取收藏列表
- `POST /api/job/history` - 记录浏览历史
- `GET /api/job/history` - 获取浏览历史

## 开发说明

### 代码规范

- 后端使用Python PEP8规范
- 前端使用ESLint规范
- 所有代码必须有中文注释

### 提交规范

- 使用语义化提交信息
- 每个功能模块单独提交
- 提交前必须通过测试

## 许可证

MIT License
