# # 更新日志

### # ICS2024

#### # NEMU

  1. 特性 
     * 提升在AM上运行时的随机性 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/fa6e67fcbbdddab62c738962072ea62b2c9e3938>))
     * 使用capstone替换LLVM进行反汇编 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/1a493f9c0b433af2fbddabeb9c186bd55ccd4ad1>))
     * DiffTest支持loongarch32r ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/8f74e3a5e6ef23cc0a0871f097e668f8992e25a2>))
     * 重新添加x86 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a738d2ea2d0194ab248c8b10c7e409e7a130b3ee>))
  2. 性能 
     * 物理内存的初始化只采用1个随机字节, 大幅提升该步骤的性能 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/4fbe3ab3ba70a2cc6af0e2698a4041e89ac4dfc0>))
     * 通过缩小局部变量的作用域提升译码过程的性能 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a264eb16edc02c23c287ddd1aad11c38da8fe366>))
  3. 修复 
     * 修复在AM上无法调用文件操作的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/feea23db1987c80b3447c7966cc11a40b9f96a51>))
     * 修复关闭窗口后仍无法退出的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/da81fe5054d69c8d14d511bdcdca816fb1bcc5fd>))
     * 修复将NEMU编译到`riscv64-nemu`时, NEMU中的ISA为`riscv32`的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/7b57ba5d759fa6c18f7923ef985ae89d138b6196>))
     * 修复在打开日志文件前调用`Log`导致段错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/fc81a8f7b4e9da6c3dff68943082e8094f41bc3c>))
     * 修复`utils.h`中`ANSI_BG_MAGENTA`的定义错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/bbbf9e3ac1cbf53ae754d19a5dcf406b630d4e1e>))
  4. 重构 
     * 将`s->isa.inst.val`简化为`s->isa.inst` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a738d2ea2d0194ab248c8b10c7e409e7a130b3ee>))
     * 添加`panic()`拦截不支持的译码类型 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/460dd550b604c15cba8c3d39631773116b919b0a>))
     * 增大IO空间 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/98bc0822da1a3025c545b34b988006408a2e1edf>))
  5. 构建 
     * 源文件无变化时无需重新链接 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/f2e7323a2fa3a110f46780fd3b41365fefa39960>))
     * 修复`CONFIG_CC`为空时导致编译失败的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/7972a459ba5932cb291057167cb3242416fcde6c>))
     * 修复在macOS上SDL2库路径错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/2fd67c07edff1f60dc4cef57d1df41f353581485>))
     * 去除无用的宏定义 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/0c64fb9e0961aaaea4780dcf10fa3219fe1fc0ba>))
  6. 文档 
     * 修复`config.mk`中的文字错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d0ca3cfda4cd96ded866a520b13a0829029a675f>))
     * 更新license中的时间 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/ba499b77d4e8cdd763750810e6ca8484c204d073>))

#### # Abstract-Machine

  1. 特性 
     * 在native中添加UART ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/493a0650ce0960e52e56d6d7500dccb56142bd08>))
     * 为npc添加`uart_config`函数 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/c383159000a2975dabde43f221deae3d54bc48b0>))
     * 为`riscv??-nemu`的`_start`符号添加大小属性 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/90ae4830e39a69c8652061a1758551a63098afb8>))
     * 添加`riscv32mini-nemu` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/56d4ae7165293bdbb06aa386d904e6a3e4621b23>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/9d1cb1d5631ba745510cc01e15a1314532fb596e>))
     * 为native新增其他架构 
       * aarch64([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/fe84c58450fd50f38bc500220b24c1f3bfbb5e70>))
       * riscv64([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/a7b830fedd86505e8accba8f4b928084542c841a>))
  2. 修复 
     * 修复`riscv??-nemu`的`trap.S`中的寄存器数量错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/f198eb6073383c1e0a5201be42b43c609082264e>))
     * 修复使用clang时libgcc中的编译错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/62ca04d426865cce1ab55483a8b1ae6a6cf71f62>))
     * 修复编译预处理指示符 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/acd889e89c8f043f74af96a3f060db777f821ee3>))
     * 修复链接时`jal`跳转距离不够的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/031dd9d93104468c7681ce3c72b1a3d1d33f6dea>))
     * 修复loongarch的`cte.c`中变量名错误导致的编译错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/6f2c34532022bbb0d0c02aac64ff174e9655fc24>))
     * 修复`x86-qemu`中boot相关的strict aliasing bug ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/de78d6ca0a5d399c55f9bae489239f5542d20fe7>))
  3. 重构 
     * 去除klib中的无用代码 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/bcdbc4e249627e7a65eb0de51ec7507c1f9bbaf1>))
     * 简单重构native GPU中`W`和`H`相关的代码 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/e6f833c3b93f42080ee90bdf286c76fa364b4df5>))
  4. 构建 
     * 去除`Makefile`的`image-dep`规则中的冗余依赖 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/3ba0c6afd76fffe249f5d076d9f631a6e6d4fe36>))
     * 避免Linux上的其他动态库链接到ELF中的符号 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/fa82955135ef6b93b711ec8c3b4e30c3a75c6fc7>))
     * 重构依赖规则 
       * 修复源文件无变化时仍然重新链接的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/c3ffbc97c39d5374c3e4f182eaaa8ae7bdc0e98e>))
       * 将`mainargs`注入到bin文件, 避免重复编译`trm.c` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/c52a41181f8ea5d0e970008e51f58867a3ce65bb>))
       * 将链接脚本添加到依赖规则 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/84051a9071557010554b6535408a15293ffa5892>))
       * 不显示native的链接命令 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/befa0459648bdf3821dc71e46673f443977ec337>))
     * `native`的IOE通过`sdl2-config`找到`SDL.h` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/61a35370c9ea634aeef69c5faacf2bb146a50230>))
     * 修复`x86-qemu`中`array subscript 0 is outside array bounds`的警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/0e37b474981568f2790f75f5d1105bbb2509515c>))

#### # am-kernels

  1. 特性 
     * 新增若干测试 
       * `yiels-os`([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/6f4a47afb9d6ca1872b52ec5ebaa0351d3549c71>))
       * `bad-apple`([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/7bb7b1a94fb13729dcc8ce4b384fff47caeb04ec>))
       * `blockchain` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/3bdc2529639606a92d23e921542fc1ec95c68af6>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/a799b79f5f470986e1cdd2b594ef1300927da0e3>))
     * 假设`uptime`不从0开始, 从而支持`typing-game`的重新运行 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/ade50b257ac81f21f82fdba6c2e9c80cc2b7a17b>))
     * benchmark出错时向TRM返回非0值 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/2e7c5934eda067ca2b116d23fb567b7090ef0a44>))
  2. 性能 
     * 加速`typing-game`清屏的过程 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/d41f447c17f387a10dee3ad750a7b5d8d0c2d264>))
  3. 修复 
     * 修复`keyboard-test`中`char`符号问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/33c0dd0d8510c27678f230b9c2799a7fe91324a0>))
     * 修复`game of life`的栈溢出问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/0c1f038ad0f50de57f806d24343ea93b102be732>))
     * 修复`hanoi`中屏幕不刷新的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/3c50c2eae3d9d001f33cae089c87cf9a51630669>))
     * 修复`alu-tests`中的若干问题 
       * 修复由`-Wall`和`-Werror`报告的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/d918fc429f330325bd331e00aa8930d4a6593704>))
       * 修复由clang报告的`-2147483648`格式错误问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/9486898b811b8e436733c2e1ca99419592c62fc5>))
     * 修复`microbench`中的`uint32_t`溢出问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/1dc914a675aa41a09762ab4a83318a481f96e429>))
     * 修复在性能较低的平台上`donut`显示时间过短的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/bb725d6f8223dd7de831c3b692e8c4531e9d01af>))
  4. 重构 
     * 为`intr-test`添加panic信息 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/86c5532674db3edf8793dc71cdc72dfb097523ec>))
  5. 构建 
     * 改进`cpu-tests`的`Makefile`输出的信息 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/dbe346eb85628a44b18d00c666883b7506dc75ea>))
  6. 文档 
     * 补充`alu-tests`和`snake`的license ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/773fa2b9972945ab1dbe1c5d675b7d2a0e6becbb>))

#### # Navy-apps

  1. 修复 
     * 修复`nplayer`中的结束判断条件 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/250084182bf17851ce2f48b7f4b7116a57163a56>))
     * 拦截libbdf中字体文件打开错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/a1ca3b9806a6addca02b5495ee99aa5071074315>))
     * 用surface相关API实现`native`的SDL渲染, 修复render API只能在主线程调用的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/b56b659255b8bd6f99e13cc484dc65d88f9f6a0f>))
     * 修复`nslider`在Linux native上无法更新画面的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/fb9d4528184fef345f1d4123116140e2336006bf>))
     * 修复`libbdf`在gcc 13上编译错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/b80605c997a22ae9f06ddf96b1aec5adc0b2b949>))
  2. 构建 
     * 修复git未追踪`scripts/riscv/common.mk`的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/d65f17be0929299822445b1f045ee074d0d56876>))
     * 修复`ar`命令在macOS中出错的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/6c8232a0519a82c8eabbf053af41053fce052599>))
     * 重构依赖规则, 修复源文件无变化时仍然重新链接的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/042a85a77d608195d3c23bbe90d0a599a130fbc1>))
  3. 文档 
     * 添加关于`/proc/dispinfo`的注释 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/e8346911c80af39b63e47d8aba5878e43231ad63>))

### # ICS2023

#### # NEMU

  1. 特性 
     * 重新添加mips32 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/76278e886803354b81d14522aa7eb71d7b810dee>))
     * 新增loongarch32r ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/6fcaae09de32aafb3bf86d26d71def11db05bbfd>))
     * 通过llvm反汇编时关闭伪指令 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/9bf4ff83597d37646098ed707f591f07d933e6bd>))
  2. 修复 
     * 修复译码非法指令时的未定义行为 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/8417a259398089bb8b590b7785f768c075548d81>))
     * 更新spike版本, 修复macOS上因llvm版本较新导致的spike编译错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/fe77a6b3a032f4ccd68da0570832518dd6475a1a>)) 
       * 使用c++17编译spike ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/5f66cb8067674512bb606e20530d8d764188fbb4>))
     * 修复`gen-expr`中`fscanf()`未检查返回值导致的编译报错 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c3baa4a77de7525cef93e19c2353b90947e86e78>))
     * 修复`nemu/src/device/keyboard.c`中宏可能与库的头文件中定义重名的问题 
       * 宏展开后重名([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/b5c841e21b2e87daedb64dd2710c0e8c38ee5aaf>))
       * 宏展开过程中重名([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/7cc6120266ba8163d4ae501017c1fcc195e556cd>))
     * 修复SDL在Wayland环境下窗口不弹出的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/03daf8795774fd9ba65454fb009daa65f66bc29a>))
  3. 重构 
     * 合并riscv32和riscv64 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/4bfdb7e3a95752d2a901ac8ea726d80b3f1b58c6>))
  4. 构建 
     * 修复C++报告的`invalid suffix on literal`警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/947dc940a9c9efcbdc798354eb71d85803bc4220>))
     * 同步config文件 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/379f440c18499e9d80e02e3a72d263bafec187cf>))
     * 修复在llvm15上库函数路径变化导致的编译错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/ed2066c1f6e7e6bfb4f8203146c5f3d1d856e348>))
     * 修复在macOS上按键宏定义与系统库冲突的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/48b4860cef80073dbac7b8d980c8d3b90f9bf152>))
     * 将difftest动态库的符号默认设置为`visibility=hidden`, 提升动态库内部符号引用的性能 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/3d5b0b9160cd37fc5d462567123bd43e48f6fac6>))
     * 修复Gentoo Linux中kconfig链接报错的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/6498a76b2742a680ac2d6fd68358b878c64b05f5>))
  5. 文档 
     * 更新启动debian的说明文档 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/f85b00d6a11bf537836e108f064603a0231ae094>))
     * 修复`difftest-def.h`中注释的文字错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/cf50554d0294a033c6048a6cd29f4544f222971c>))

#### # Abstract-Machine

  1. 特性 
     * 新增`loongarch32r-nemu` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/67699be876bd5afe4fc7ddf48b7363871120de0b>))
     * 将`riscv64-npc`改为`riscv32e-npc` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/d341fb23a0d3e032e93ca3d3486f7622450e2a72>)) 
       * 为`riscv32e-npc`添加libgcc的若干支持, 用软件模拟乘除指令 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/a4d3661c31570eec6c87be650f6446bdd6099ea8>))
     * 添加用于生成logisim镜像文件的python脚本 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/83ac97b4d90c2f4cdd0ecc043a93885d0d3c29a1>))
  2. 修复 
     * 在mips32的`start.S`中为异常入口`0x80000180`预留若干位置, 用于设置异常入口处的执行 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/5051c13e02f657e87609c2bad17709155019c39c>))
     * 修复sdl2-2.0.22-1后窗口有概率不显示的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/ba5ba9838edcdef5cc8d7b436124af655ada36d1>))
     * 修复native的`platform.c`链接到RT-Thread中`ftruncate()`的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/21bfbcb293567804c9617e5ceb374f94f4bc32ed>))
     * 修复`riscv.h`中通用寄存器数量在rve中不正确的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/b1586e033693a3616b988200658342d6ff90569c>))
     * 修复`riscv32-nemu`中错误采用rve ABI的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/8878f1f6ce19c3fa0d9a9414e7a8c121116f31e1>))
  3. 重构 
     * 将`scripts/isa/`目录下RISC-V相关的`.mk`文件合并成`riscv.mk` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/ad8f8fb636925666d2fb9a2216da868b82ba0e5b>))
     * 将`am/include/arch/`目录下RISC-V相关的`.h`文件合并成`riscv.h` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/e0ae9b7651436f8dfcbe6383f73f67ebb04ce399>))
  4. 构建 
     * 去除ld 2.39引入的关于可执行栈和可读可写可执行的可加载段的警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/024441cbed3e9889fe62503f34df5d6c3fa08170>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/31a5a10f4858096751329b5a9b8a671ba819b1ea>))
     * 使用riscv64-linux-gnu-gcc 11将CSR指令独立成zicsr扩展, 修复相关编译错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/ad9504123fba7548ca41b1295664d1f9928b5052>))
     * 支持将`LDFLAGS`传递给native的g++ ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/e8943b31fc30adaba4fded6b8e9eb4f73477e491>))
     * 修复macOS上默认调用llvm-ar的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/6d79d0efb082c5346c99fab1f1d67cb996f169f7>))

#### # am-kernels

  1. 特性 
     * 新增ALU test, bf等应用, 移植自[movfuscator项目在新窗口中打开](<https://github.com/xoreaxeaxeax/movfuscator>) ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/fbc27398751336619ed4242349fe4567b9bf82d5>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/d336e55bc38e8a4c2f263b562b02e8b95defdab2>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/6b5c2ad2d3cdfa24935e60ba5c4d166eb1ca94f4>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/b122a7fa12f13ccbde94c645f309f32325195149>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/1cf8c67eb673d2e344b1ae874c3d51f1e7c23d96>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/ec82e0f2cd389bfe0fa582244601af9ef70158b2>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/3388801aea9d288ed598fc3c66c6412f3460b0d2>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/c5bcf378e8de01ca1cf695ebcc36b8c7e0def2c9>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/4707aefcc525e7d25b4d3de941287acd0c7c14da>))
  2. 修复 
     * 修复native在glibc 2.39上运行thread-os时发生栈溢出的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/245c069c4efae82358a292a2d9dbdf9c1584fcbc>))
  3. 重构 
     * 去除`cpu-tests`中冗余的klib依赖 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/53cc98e4c02fc44aab3d8595d451ff78aa15308f>))

#### # Navy-Apps

  1. 特性 
     * 新增loongarch32r ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/a0917289765288f1622e69d46666ab4540e7584c>))
     * 新增riscv32e ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/0e782aa991e68b456c3cee4233b95c2ba4c7b820>))
  2. 修复 
     * 修复native在glibc 2.39上段错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/fd219c457db2b83a6e36f007079a6025b6fb3d1f>))
     * 修复`LD_PRELOAD`影响gdb的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/378380f4ecf51c4d65f4a475bdf66a91e95913db>))
  3. 重构 
     * 将CRT中`_start`的定义集中在一个文件中, 方便使用`__riscv`宏进行判断 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/8fe76b4e50cc03c2d17e284f57f9e0d6e80e0c2f>))
  4. 构建 
     * 添加缺失的文件`scripts/riscv/common.mk` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/754fea853eaa91baf448b20464adb37f53798dff>))
  5. 文档 
     * 修复`README.md`中的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/f7209826eebd4011ac4a5d97f2a880e9c71d17c7>))

### # ICS2022

#### # NEMU

  1. 特性 
     * 移除指令实现的IR层
     * 支持向spike注入中断
     * 使用LLVM库进行反汇编 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/58f009646bb6e2448f79486013f22d56d99c15a1>))
     * 添加NEMU作为REF的API(一生一芯中使用) ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/55e43218041ddacd4487b4bdc4e15251b4ab9e03>))
     * 添加MMIO区间重叠的检查 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a1813e5e6f1ae0668da31d76b04517a189924068>))
  2. 修复 
     * 修复spike段错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/1b5a19b1975142d44797b7418aeebff458d52dbd>))
     * 修复监视点初始化时的数组溢出问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c02f89e0a88202ef497bbf048c105790c67626c8>))
     * 修复`isa_logo`字符串缺少`\0`的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/2e3773f9bb5581be6b4e7092955eb7215137bf9f>))
     * 去掉RTL中间表示, 用"抄手册"宏重构译码部分 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/6892cee4d95ff628d878b4a0f6a9f887c9d5d626>))
     * 修复`difftest_init()`中缺少的参数 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/af274458f2c0491cf3e5b4bd2520336057f531c0>))
     * 修复因`optind`重定位错误导致spike触发段错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/8521f46acae2ada40ad067a4c0513f504cdd42d7>))
     * 修复移位运算的未定义行为 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/ae8715807dc482db6f6e8f40efc38fcf9d4bc9f4>))
     * 修复`ANSI`文字错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a51185885fd23e411817014eaf820c8fe3eb589d>))
     * 修复PMEM64的`printf`格式错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/32f212facc126f5a6d45cfb3a8276ef7b7d3d0c3>))
     * 修复pmem右边界的计算 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/e9fd223f3d6c793c8ce5732ff183b9b98d3787d9>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/404746d04d0e1cfffe9d801bf9e3be05e03cd295>))
     * 修复字符串中的文字错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c0ecbb498aca635d9da3d179e1daaf5001b08775>))
     * 修复`uint64_t`的格式说明符 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c52dfec86a496a2399ef0aa1f8b54584ab3b7ce6>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/bf47a5911819fc1010f5d649f784113afa06b026>))
  3. 重构 
     * 将`instr`重命名为`inst`
     * 去掉调用`dlopen()`时不使用的`RTLD_DEEPBIND` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d2de05d7d3f2ef8ae13403bc687be4a1a19c4aac>))
     * 交换itrace中输出的字节序, 使其符合RISC-V的阅读习惯 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/161eb8dcc4ed1616f9e70db8d32bb31b80dd4697>))
     * 重构物理内存左右边界的计算 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/4965f34aaac0cfa42030844c95110fd79dc61a7a>))
     * 简化`INSTPAT`的写法 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/09bb925782871ed4eb98d17cfabab323d473df62>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/4aad1d6de344251c9c6c755fd000c30f199cbb24>))
  4. 构建 
     * 修复`clean-tools`错误清除spike中子项目的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/e9b9e4a9d7c792f5784f60c031ad0e0aa10819e5>))
     * 修复git忽略追踪`disasm.cc`的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/9fffdce8f8394b022ae3815f625408889dd6ec9b>))
     * 支持多个LLVM版本 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c24a93e6b21795fca269be4fe04d280e1e382960>)和 [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d21e335ca8903670db422a8717956fa5c7fa92a3>))
     * 使用`ics-pa`项目中的git函数 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d7a7a000f36f9b5a309c509eebdea8f18e6f523c>))
     * 默认关闭设备 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/030c87652479a84b9449d7f66ffafbae07a6551c>))
     * 修复采用`-g`编译时的LLVM相关的警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d114445d797c2782ee0ba597b6397f83c622f482>))
     * 使用ssh从github上克隆spike ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d65fa540caf35cf1a7e42b26de1fe09dbca7cc42>))
     * 修复LLVM 14中头文件`TargetRegistry.h`移动导致的错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a0a70ead187a928ad4e55cf3a5c72ef8a3734475>))
     * LLVM版本小于11时报错 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/541d969d9280ffd60e6a94577c4bd3b9141e0bd5>))
     * 去除`kconfig`中冗余的动态库`-ltinfo` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/ea9758d0310d822a503761939b7f9f8dacb51470>))
  5. 文档 
     * 添加license ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/29fd6af58df98ff102f09ff68a3e0972b13c1e99>))

#### # Abstract-Machine

  1. 特性 
     * `riscv64-npc`支持乘除法指令 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/89939ad7a2b2d7d92d4f72f4db33a48b9d0341eb>))
     * 使用标准调试指令实现`nemu_trap` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/d5fe878987b6f4b547c81b71897eabb7fb250940>))
  2. 修复 
     * 修复定义`__NATIVE_USE_KLIB__`时的死递归 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/f9b9b390fb673cee2d733106db077efda65bb304>))
  3. 构建 
     * 默认使用通常模式(而不是批处理模式)来运行NEMU ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/198ce9035281a5bc041c7b3213c2a3daacc091fa>))
     * 修复ubuntu 21.10下因glibc中的`SIGSTKSZ`展开为函数调用而导致native编译出错的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/112799e02a28d22f03cfe496fe36408112047a71>)) 
       * 放宽`SIGSTKSZ`的检查条件 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/7c9b27be201ba70fa7793cab7efe822d8e951eee>))

#### # am-kernels

  1. 构建 
     * `cpu-tests`支持gdb目标 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/adc316af6e482e6444a9bd68bafc3a57e2cafdbc>))

#### # Nanos-lite

  1. 修复 
     * 修复`sizeof(struct timeval)`在glibc和newlib中不一致的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nanos-lite/commit/2a141760e31be246a7316942293a97873925bc2f>))

#### # Navy-apps

  1. 构建 
     * 使用ssh从github上克隆子仓库 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/13ba3997899ca9fe83e4c4c98a498ea06d41cfdd>))

### # ICS2021

#### # NEMU

  1. 特性 
     * 为VGA添加sync寄存器 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/7e4bfdfc0c6058b6c488c4e05bfa06f8fb426795>))
     * 添加riscv64 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/828ff8118f18de2079f08d1d658a80277a30a3bf>))
     * 引入"抄手册宏", 简化操作码译码的实现 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/9edc3ac03d3a67c7fb368c1e6fb703b155293454>))
     * 添加spike作为RISC-V DiffTest的REF
     * 暂时移除x86和mips
     * 移除`cpu-tests`的一键运行脚本, 将其合并到`cpu-tests`中
     * 添加各种对宏进行相关测试的宏定义
     * 添加一些将来可能会使用的资源, 包括启动Debian的说明, SD卡内核驱动等
     * 在`cpu_exec()`中调用`device_update()` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d9c2c749072e73b97e2b01d033d88c43ebc29d9b>))
  2. 修复 
     * 修复`PMEM_SIZE`设置与讲义不一致的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/c880b79490b33824995bfa4eb78b5f258ea735c5>))
     * 修复文字错误`fecth` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/0815e787a13dc6aa1dbafd7b7e6e7a4dadaf10d0>))
     * 修复框架代码`audio_play()`未使用的编译警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/5536f2c5ae35e1d6683d7326908451069c43325e>))
     * 修复`BITMASK`宏中的移位操作的未定义行为 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/b4cf42b47bf2b9ecb75e3ec5f9d850a1fef67057>))
     * 修复`qemu-diff`中调用`calloc()`时的类型错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/91f932c6e1b921769e949b1f6844ed9a2da31399>))
     * 修复`config.mk`中的文字错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/61e0cb43c31a46af6b2c75f57f718f027ae8e2f4>))
     * 修复`MEM_RET_FAIL`与`MMU_TRANSLATE`的数值冲突的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/7538d373a6e32088fff4000deace39d04ba329e0>))
  3. 重构 
     * 去除`gen-expr`中的无用代码 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/dd5539c3f4e7306de7238ff47a83444ebc360f2d>))
     * 将简易调试器命名为`sdb`
     * 添加`hostcall()`来封装计算指令以外的操作
     * 用`host_read()`/`host_write()`实现`pmem_read()`和`pmem_write()`
     * 添加`mmio_read()`/`mmio_write()`
     * 将部分功能实现放到`utils/`目录下
     * 重构`qemu-diff`中ISA相关的代码
     * 将`load_val`重命名为`is_write` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/b9af1ea9abd93b169254ec6c4d3e6af55780a513>))
     * 用`dnpc`更新`pc` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/2bcb4d4cbfe4e1d2ba11b84126f2bd363216345d>))
     * 将移位指令的命名修改成RISC-V风格 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/a1de894d42d83f31d54bff924a193e1b20ec86da>))
     * 去除无用的`isa_mmu_state()` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/b2371b1e16e9ab4af54f2ef66baf924aa10343bf>))
     * 去除无用的`isa_hostcall()` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/fe1f041fae05221b1db5ca768ba5b7eec9d968cc>))
  4. 构建 
     * 添加`Kconfig`和`menuconfig`维护宏定义
     * 将`Makefile`拆成`build.mk`和`native.mk`, 前者用于在构建`tools/`目录下的工具时复用
     * 在`Makefile`中采用filelist维护需要编译的源文件
     * 支持将NEMU编译到AM
     * 去除`build.mk`中无用的`SO_CFLAGS` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/2e014f5d6bc8d7211491a8547747211945e7fce4>))
  5. 文档 
     * 在`Makefile`中添加注释 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/25ddea72b44035810a7c19bc4866c678a12b7dd2>))
     * 修复`isa_raise_intr()`中的注释 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nemu/commit/d80266ebcb5b38d89d88c061487eb436adcefdc0>))

#### # Abstract-Machine

  1. 特性 
     * NEMU的GPU通过向sync寄存器写入非零值实现屏幕的刷新 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/98ff649a54198edb6f4ee2720dc8bb8b9e2f878f>))
     * `native`的堆区移动到`0x1000000`, 以支持用户程序可在VME关闭时访问 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/39b2c4350d46cd415860356239d6c4d8ba61cf92>))
     * `native`的GPU支持800x600模式 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/e4e5d03fa6dc52795e66ac2693e0fe0e0d85c9af>))
     * 添加`riscv64-nemu` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/11059d5b6fbdb79ae2d22f4ce495ec04d20bf59e>))
     * 强制`native`初始化时链接到glibc中的`memcpy()`, 在klib中的`memcpy()`实现不正确的情况下也能工作
     * 为NEMU添加单核的MPE实现
     * 支持`x86_64-qemu`的交叉编译
     * 添加`riscv64-mycpu`(一生一芯中使用) ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/1a4ad391764a7e160ad99e5fbf2b9d096ad25234>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/17037fabb0d877f2568490cdc035e3a28085848d>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/07eb9ba416c5207013d10c4b57667fce9ca4f809>), [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/01d76dd0d56b00400cdeb89636a95d8a7ee6f0bf>))
     * 添加spike ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/3cf0ee6d428d1eb6348fa0ee6c2e3c7f8a746363>))
  2. 性能 
     * 移除`native`在物理内存上的保护功能, 减少系统调用以提升性能 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/18995de2698b26140b660271054a1a37336e3f67>))
     * 用哈希表实现`native`的`map()`中的虚地址查找
  3. 修复 
     * 修复Linux 4.19内核中因恢复FPU上下文时`fxrstor64`指令触发缺页而发送`SIGSEGV`的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/66dcd98e39b6cd93c49dcc2b8ca38495d30db075>))
     * 修复`native`在信号处理函数中调用非信号安全函数`printf()`的问题
     * 修复`amdev.h`被多次包含造成的问题
     * 修复在`native`上运行仙剑时遇到的`SIGFPE`问题, 需要在调用`SDL_BlitSurface`前清除等待中的FPU异常
     * 修复`riscv64-mycpu`模拟除法时的死递归问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/3364f57d0bf5f31f91d5b1214a7a7b17e975c049>))
     * 修复静态库的循环依赖问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/3c2e025216938332206c6011951365fd5088ad3b>))
  4. 重构 
     * 移除`x86-nemu`中无用的`usp` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/55ef7b162d0466cacac0a7e96f1c7007f85752fc>))
     * 在`native`中使用`SIGUSR2`实现`yield()`, 提升代码的可移植性
     * 在`native`中使用函数调用从`irq_handle()`返回, 提升代码的可移植性
     * 用surface相关API实现`native`的SDL渲染
     * 将`native`平台相关的代码移动到`platform.c`中
     * 用管道实现`native`声卡中的数据同步
     * 去除`boot`目录
     * 将`__amkcontext_start`重命名为`__am_kcontext_start`
     * klib中的函数默认调用`panic()`
     * 重构目录, 合并riscv32和riscv64 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/30e5cd0c7e50d19d7fde4f95c6d0ff8edbad5c1b>))
  5. 构建 
     * 清理NEMU客户程序中未使用的代码和数据 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/a1c8ab14d1bc71bb80eea720ad00a4c87615f7f0>))
     * 去除Ubuntu 20.04中在Comet Lake以上版本的CPU中编译出的`endbr32`指令 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/0f6f91dee305ad0b143bf13becc2882eda4d977a>))
     * 待构建源文件列表为空时提示错误信息
     * 若交叉编译器不存在, 则使用本地编译器
     * 不同的架构复用相同的链接脚本
     * 在mk文件中指定AM相关的源文件 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/30e5cd0c7e50d19d7fde4f95c6d0ff8edbad5c1b>))
     * 在Ubuntu中禁用栈保护 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/abstract-machine/commit/a873515bde26f4ee0826d5e0c7c4df700e6ebe77>))
  6. 文档 
     * 完善`Makefile`中的注释

#### # am-kernels

  1. 特性 
     * `microbench`的时间精度提升至`us` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/f4f447c422d46f866bbd5ec5d871eef2407c03b5>))
     * `microbench`添加`huge`规模输入, 用于真机测试 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/54f5c1f8faffc956cc195578563fc67be6f42c88>)和) [补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/e611fa70d2e156c93adb4d002cce145defa17d05>))
     * `microbench`的参考机器更换为`i9-9900k` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/e45d2189d9ea0644e22c4e6b04ad3d40dc7393bf>))
     * `cpu-tests`支持一键运行的结果统计 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/56c864d5eff587138e26149616bd129c35e230bc>))
     * 支持将NEMU编译到AM ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/6052ab0244aa06b033eed47313c42093f9cc5e4b>))
     * 当NEMU未成功编译到AM时, 恢复之前的config配置 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/c03fc2b97bbab2f5f37a41c991cd31d905a740b1>))
  2. 修复 
     * 修复`cpu-tests`的`string`测试中`strcmp()`的返回值检查 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/242c1f1f53a5c38268c68b0827e655296431358d>))
     * 修复`litenes`中多重定义的链接错误 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/87c35f8f19aa0545a1e78a81020b9c105e76e87d>))
  3. 重构 
     * 在`microbench`中显式使用`uint32_t`和`uint64_t` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/1a008865df39382cf9bc6f5afa5a0eae34686513>))
     * 由`microbench`自行对`us`部分进行输出格式化, 避免对`%03d`的依赖 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/a3d742d2592ef7b6135f0f93c460320cc3304c07>))
     * 将`am-tests`中`intr-test`的`pirntf()`换成`putch()`, 降低对klib的依赖 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/5e7cd0c7f237e1b276674245c733bbcfe055bd55>))
  4. 构建 
     * 移除`cpu-tests`中不再使用的构建规则 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/f3af11ebbfeab009a2213f9ca534e9a802a64235>))
     * 取消部分文件的可执行权限 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/am-kernels/commit/8a1caa1db35077367ec83757b90b6be160021200>))

#### # Nanos-lite

  1. 修复 
     * 修复`HAS_NAVY=0`时依赖错误的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nanos-lite/commit/a5a1a3dbfa7f4f5d1b25fb834572544bf04fbbbb>))
     * 修复框架代码`pg_alloc()`未使用的编译警告 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/nanos-lite/commit/04ae868da1e100fb3199e8f1baf1ebbed3368501>))

#### # Navy-apps

  1. 特性 
     * 添加`riscv64`的支持 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/0de5de8d21e68ff3f4d732cb17fd100f13461cc9>))
  2. 修复 
     * 修复NWM在退出时子进程仍然运行的问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/1b68cecfd71e3964a446a982ae36136c651fe543>))
     * 修复`libbdf`和`libbmp`调用`SDL_CreateRGBSurfaceFrom`后的内存泄漏问题 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/8a2f3d910b5228a4c5415b888e7da0b8390aacd5>))
  3. 重构 
     * `libminiSDL`将`fp`从`SDL_RWops`的`union`成员中取出, 从而允许通过`fmemopen`实现内存文件 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/603b7b776860b82e6b69cd28e14fec1ad3957259>))
     * `libSDL_image`中要求`IMG_Load_RW()`的`freesrc`参数为`0` ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/603b7b776860b82e6b69cd28e14fec1ad3957259>))
  4. 构建 
     * 令`ramdisk.img`大小为512字节的整数倍, 从而易于实现磁盘的特性 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/88a384c7f5b65380c5797b7589342442d6f44279>))
     * 去除`make clean-all`时的警告信息 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/e853ea70d08a17a3f7b7dbeeed8bf06fe20fd4d4>))
     * `make init`时不检查`ISA`是否合法 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/fb4f7184883917de77e85e6568637464ef6b7860>))
     * `make install`时自动创建`fsimg/bin/`目录 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/da22c2f16559c461d1f420bc22ff2481900ad95e>))
  5. 文档 
     * `libSDL_mixer`支持不同频率不同声道的多通道混声 ([补丁在新窗口中打开](<https://github.com/NJU-ProjectN/navy-apps/commit/603b7b776860b82e6b69cd28e14fec1ad3957259>))

[ NEMU ISA相关的API说明文档 ](</docs/ics-pa/nemu-isa-api.html>)[ x86指令系统简介 ](</docs/ics-pa/i386-intro.html>)
