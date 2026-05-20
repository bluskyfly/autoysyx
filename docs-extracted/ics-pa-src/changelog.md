# 更新日志

_source: https://ysyx.oscc.cc/ics-pa-src/changelog.html_

## Outline
-   [ICS2024](#ics2024)
-   [ICS2023](#ics2023)
-   [ICS2022](#ics2022)
-   [ICS2021](#ics2021)

---

- 在`native`中使用`SIGUSR2`实现`yield()`, 提升代码的可移植性
- 在`native`中使用函数调用从`irq_handle()`返回, 提升代码的可移植性
- 用surface相关API实现`native`的SDL渲染
- 将`native`平台相关的代码移动到`platform.c`中
- 用管道实现`native`声卡中的数据同步
- 去除`boot`目录
- 将`__amkcontext_start`重命名为`__am_kcontext_start`
- klib中的函数默认调用`panic()`

- 将简易调试器命名为`sdb`
- 添加`hostcall()`来封装计算指令以外的操作
- 用`host_read()`/`host_write()`实现`pmem_read()`和`pmem_write()`
- 添加`mmio_read()`/`mmio_write()`
- 将部分功能实现放到`utils/`目录下
- 重构`qemu-diff`中ISA相关的代码

- 修复`native`在信号处理函数中调用非信号安全函数`printf()`的问题
- 修复`amdev.h`被多次包含造成的问题
- 修复在`native`上运行仙剑时遇到的`SIGFPE`问题, 需要在调用`SDL_BlitSurface`前清除等待中的FPU异常

- 添加`Kconfig`和`menuconfig`维护宏定义
- 将`Makefile`拆成`build.mk`和`native.mk`, 前者用于在构建`tools/`目录下的工具时复用
- 在`Makefile`中采用filelist维护需要编译的源文件
- 支持将NEMU编译到AM

# [#](#更新日志) 更新日志

### [#](#ics2024) ICS2024

#### [#](#nemu) NEMU
