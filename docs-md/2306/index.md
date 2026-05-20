# # 第六期"一生一芯"课程主页

  * 课时: 每周六15:00~17:00 
    * [B站直播在新窗口中打开](<https://live.bilibili.com/24416626>) | [录播链接在新窗口中打开](<https://space.bilibili.com/2107852263/channel/collectiondetail?sid=1523995>)
  * 如果你发现了实验讲义和材料的错误或者对实验内容有疑问或建议, 可通过邮件联系余子濠(yuzihao#ict.ac.cn)

## # 学习目标

"一生一芯"将会培养大家的综合能力. 大家完成学习之后, 将会对以下问题有一定的认识:

  1. 处理器是如何设计的?
  2. 程序是如何在计算机上运行的?
  3. 如何对处理器的性能进行优化?
  4. 如何使用/设计正确的工具高效地进行调试?
  5. 如何自己编写测试用例进行单元测试?
  6. RTL设计如何生成可流片的版图?

我们将会引导大家设计一款RISC-V流水线处理器, 并在自己设计的处理器上运行操作系统, 在操作系统上运行真实游戏. 达成指标的处理器将可以接入到SoC, 并获得流片机会.

## # 教学资源

  * `时间`一栏是以小时为单位的预估完成时间 
    * 预估完成时间为`2`的内容, 一般没有相关的编程任务, 只有2小时的视频录播, 用于补充讲解相关知识
    * 鉴于同学们的基础水平有高有低, 此处按照"中等水平"同学的能力来预估. 但这里的"中等水平"并不是指"程序设计课程总评80分以上", 而是指"学习心态端正, 编写过500行以上代码的单个程序, 并且懂得调试".
    * 如果你是零基础的初学者, 你应该预期花费这个数字`2~3`倍的时间来完成学习. 不过你不必为此感到沮丧, 所谓"闻道有先后", 之所以其他同学学得快, 很大一部分原因是因为他们之前已经付出努力迈过了初学者的阶段.
  * 可点击图标跳转到相应资源
  * 完整的讲义可通过页面右上方导航栏查看
  * 课件用[reveal.js在新窗口中打开](<https://revealjs.com>)编写, 可导出为PDF文件, 具体见[这里的操作在新窗口中打开](<https://revealjs.com/pdf-export/>)
  * S阶段讲义内容仍然在🕊

`C` = C语言(程序/模拟器/系统软件) | `R` = RISC-V指令集 | `P` = 处理器设计 | `T` = 工具

阶段 | 序号| 任务 | 时间 | 讲义 | 课件 | 视频| C | R | P | T  
---|---|---|---|---|---|---|---|---|---|---  
预学习阶段|  | 如何科学地提问 | 2| [📚](<../2306/preliminary/0.1.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/01.html#/>)| [🎬](<https://www.bilibili.com/video/BV14F411975K>)|  |  |  |   
| Linux系统安装和基本使用 | 10| [📚](<../2306/preliminary/0.2.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/02.html#/>)| [🎬](<https://www.bilibili.com/video/BV1vF4119726>)|  |  |  |   
| 计算机系统的状态机模型 | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/03.html#/>)| [🎬](<https://www.bilibili.com/video/BV1oN411Y7FK>)|  |  |  |   
| 复习C语言 | 20| [📚](<../2306/preliminary/0.3.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/04.html#/>)| [🎬](<https://www.bilibili.com/video/BV13z4y147mB>)|  |  |  |   
| 程序的执行和模拟器 | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/05.html#/>)| [🎬](<https://www.bilibili.com/video/BV1Rm4y1p7Cg>)|  |  |  |   
| 搭建verilator仿真环境 | 5| [📚](<../2306/preliminary/0.4.html>)|  \- |  \- |  |  |  |   
| 数字电路基础实验 | 20| [📚](<../2306/preliminary/0.5.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/06.html#/>)| [🎬](<https://www.bilibili.com/video/BV1ZH4y1Q7Cv>)|  |  |  |   
| 完成PA1 | 30| [📚](<../2306/preliminary/0.6.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/07.html#/>)| [🎬](<https://www.bilibili.com/video/BV1up4y1j7Ji>)|  |  |  |   
__申请入学答辩  
基础阶段|  | 支持RV32IM的NEMU | 10| [📚](<../2306/basic/1.1.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/08.html#/>)| [🎬](<https://www.bilibili.com/video/BV15h4y1A7Up>)|  |  |  |   
| 程序的机器级表示(上) | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/09.html#/>)| [🎬](<https://www.bilibili.com/video/BV1ow411275B>)|  |  |  |   
| 程序的机器级表示(下) | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/10.html#/>)| [🎬](<https://www.bilibili.com/video/BV19H4y1d7Yi>)|  |  |  |   
| 用RTL实现最简单的处理器 | 5| [📚](<../2306/basic/1.2.html>)|  \- |  \- |  |  |  |   
| AM运行时环境 | 5| [📚](<../2306/basic/1.3.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/11.html#/>)| [🎬](<https://www.bilibili.com/video/BV1Vu4y1s73Y>)|  |  |  |   
| 工具和基础设施 | 5|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/12.html#/>)| [🎬](<https://www.bilibili.com/video/BV1RM411Q7Au>)|  |  |  |   
| 支持RV32E的单周期NPC | 10| [📚](<../2306/basic/1.4.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/13.html#/>)| [🎬](<https://www.bilibili.com/video/BV1rc411f7mK>)|  |  |  |   
| ELF文件和链接 | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/14.html#/>)| [🎬](<https://www.bilibili.com/video/BV1Ly4y1w7hn>)|  |  |  |   
| 设备和输入输出 | 10| [📚](<../2306/basic/1.5.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/15.html#/>)| [🎬](<https://www.bilibili.com/video/BV1sb4y1g7Xu>)|  |  |  |   
| 调试技巧 | 2|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/16.html#/>)| [🎬](<https://www.bilibili.com/video/BV1Vz4y1A7Rt>)|  |  |  |   
| 异常处理和RT-Thread | 15| [📚](<../2306/basic/1.6.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/17.html#/>)| [🎬](<https://www.bilibili.com/video/BV1734y1w7ro>)|  |  |  |   
| 总线 | 10| [📚](<../2306/basic/1.7.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/18.html#/>)| [🎬](<https://www.bilibili.com/video/BV1gj411s7ah>)|  |  |  |   
| SoC计算机系统(上) | 15| [📚](<../2306/basic/1.8.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/19.html#/>)| [🎬](<https://www.bilibili.com/video/BV1NC4y1u7K3>)|  |  |  |   
| SoC计算机系统(下) | 15| [📚](<../2306/basic/1.8.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/20.html#/>)| [🎬](<https://www.bilibili.com/video/BV1FC4y1k7mP>)|  |  |  |   
| 性能优化和简易缓存 | 20| [📚](<../2306/basic/1.9.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/21.html#/>)| [🎬](<https://www.bilibili.com/video/BV1xr421F7ZP>)|  |  |  |   
| 流水线处理器 | 20| [📚](<../2306/basic/1.10.html>)| [📰](<https://ysyx.oscc.cc/slides/2306/22.html#/>)| [🎬](<https://www.bilibili.com/video/BV1ZRtkeVEqw>)|  |  |  |   
[__B阶段流片准备与考核 📚](<../2306/basic/1.11.html>)  
[ __课程总结 📚](<https://ysyx.oscc.cc/slides/2306/28.html#/>)  
进阶阶段|  | 由于时间关系, 详细的A阶段讲义无法按时发布. 我们先列出[一些大纲📚](<../2306/advanced/advanced.html>), 感兴趣的同学可以按照我们给出的方向自行探索.  | 0|  |  | |  |  |  |   
专家阶段(香山邀请报告)|  | 高性能处理器的性能测算基础 | 0|  \- |  \- | [🎬](<https://www.bilibili.com/video/BV1hM4m1Z7Vd>)|  |  |  |   
| 乱序访存单元入门 | 0|  \- |  \- | [🎬](<https://www.bilibili.com/video/BV1Qy411b7GT>)|  |  |  |   
| 香山处理器昆明湖架构前端设计 | 0|  \- |  \- | [🎬](<https://www.bilibili.com/video/BV1Kb421H7RD>)|  |  |  |   
| 处理器乱序执行基础 | 0|  \- |  \- | [🎬](<https://www.bilibili.com/video/BV1nw4m1e77C>)|  |  |  |   
| 缓存基础与香山缓存 | 0|  \- |  \- | [🎬](<https://www.bilibili.com/video/BV1oM4m12726>)|  |  |  |   
总结 |  | 课程总结 | 0|  \- | [📰](<https://ysyx.oscc.cc/slides/2306/28.html#/>)| [🎬](<https://www.bilibili.com/video/BV16US2Y8E78>)|  |  |  |   
  
#### __页面加载条卡住了？

跳转页面时, 如果进度条卡住 3 秒以上, 很可能是由于我们推送了网页版本更新.  
鉴于我们还在频繁更新、修订文档, 近期可能会比较容易遇到跳转卡住的情况.  
遇到这种情况, 只需要 **`刷新整个页面`** 即可继续学习咯

## # 往期课程主页

可通过顶部导航栏的"课程主页"查看.

## # 其他资源

  * [《RISC-V开放架构设计之道》 大卫·帕特森 安德鲁·沃特曼 著，勾凌睿 陈璐 刘志刚 译在新窗口中打开](<https://item.jd.com/10092349081102.html>)
  * [《计算机系统——基于RISC-V+Linux平台》 袁春风 余子濠 陈璐 编著在新窗口中打开](<https://product.dangdang.com/29720521.html>)
  * [Digital Design and Computer Architecture - Spring 2023, Onur Mutlu@ETH Zurich在新窗口中打开](<https://safari.ethz.ch/digitaltechnik/spring2023/doku.php?id=schedule>)
  * [提问模板](</docs/2205/misc/ask.html>)

## # 活动记录

  * 2024/07/14 - [“一生一芯”2024暑期宣讲会在新窗口中打开](<https://space.bilibili.com/2107852263/channel/collectiondetail?sid=3416378>)
  * 2023/08/25 - [开源芯片技术生态论坛（原“一生一芯”技术论坛）](</docs/events/20230825-2nd-tech-forum.html>)
  * 2023/07/02 - [第六期“一生一芯”启动会在新窗口中打开](<https://space.bilibili.com/2107852263/channel/collectiondetail?sid=1497409>)
  * 2022/11/20 - [从软件工程视角看芯片开源与敏捷设计(包云岗)在新窗口中打开](<https://www.bilibili.com/video/BV1Dd4y1474D/>)
  * 2022/08/28 - [第一届“一生一芯”技术论坛暨第五期启动会](</docs/events/20220828-1st-tech-forum.html>)
  * 2022/03/12 - [软硬件协同能力在芯片设计中的应用(金越, 胡博涵, 高泽宇)在新窗口中打开](<https://www.bilibili.com/video/BV1334y187zC/>)

最近更新时间: 

贡献者: Zihao Yu, myyerrol
