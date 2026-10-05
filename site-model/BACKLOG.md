# Y-1 场地模型：待办 / 细化备忘录

最后更新：2026-10-05。每一项写明：要做什么、用什么数据、现状。
优先级：⭐⭐⭐ 影响网页上的识别度或数据正确性｜⭐⭐ 明显提升｜⭐ 锦上添花

---

## 1. 树木

- [ ] ⭐⭐⭐ **加入树种资料**
  - 数据：`references/AngelsLanding_IS-2_TreeInventory.pdf`，第 15–44 页是逐棵树的表格，有编号、树种、胸径 DBH、高度、树冠，第 14 页是位置图（KPFF Design Survey 底图）。
  - 做法：
    1. 把位置图对位到模型坐标（用地块边界和街角做控制点，方法和 `georef_plotplan.py` 一样）；
    2. 把清单上的树和 LiDAR 识别出的树按距离配对（`data/trees.json`）；
    3. 配上的树用清单里的树种，没配上的保留 LiDAR 结果。
  - 现状：229 棵树全部是同一种“椭球树冠 + 树干”。
- [ ] ⭐⭐ **按树种做不同的树形**：棕榈（细高的树干 + 一簇顶冠）、阔叶乔木、灌木。每种做一个共享网格，GLB 不会变大。
- [ ] ⭐⭐ **核对数量差异**：LiDAR 在 951 地块里识别出 90 棵，2018 年清单约 128 棵。逐棵对照后，区分是漏识别（树冠重叠、低于 3 m）还是树已经不在了。
- [ ] ⭐ 识别加密区以外的树（现在只做了 Y-1 周边约 184 × 178 m）。
- [ ] ⭐ 识别并去掉 MOCA 屋顶露台上那几丛植物在屋顶网格上形成的鼓包，或者换成树。

## 2. MOCA

- [ ] ⭐⭐ **材质分区**：红砂岩体块、绿色立方体、筒形拱顶（金属屋面）、金字塔天窗。现在整栋是一种红色。参考 `references/moca/archeyes_64.jpg`。
- [ ] ⭐⭐ **把筒形拱顶和南侧约 10 条采光脊拟合成干净的几何体**，方法同金字塔，代码在 `prep_moca.py`。现在它们还是 0.5 m 栅格表面，近看会粗糙。
- [ ] ⭐ 入口拱门通道、立面上的窗。
- [ ] ⭐ 下沉庭院和地下展厅（LiDAR 看不到，要找剖面图）。
- 已知：ArchEyes 上标为 “MOCA floor plan” 的那张图应该是 California Plaza，不是 MOCA，不要拿来用。

## 3. Metro Pershing Square 西北出入口

- [ ] ⭐⭐ **扶梯朝向**：现在假设是从北端往南下，需要照片或 Metro 的图纸确认。
- [ ] ⭐⭐ **桅杆高度和位置**：现在按你给的那张照片估计为约 10 m；短柱的位置也是估的。最好再找一张从北侧或正侧面拍的照片。
- [ ] ⭐ 雨棚的玻璃百叶（照片里是一排排的条形玻璃）。
- [ ] ⭐ 电梯出入口（SubwayNut 的照片里有花岗岩方盒和电梯，位置还没确认）。

## 4. Angels Flight

- [ ] ⭐⭐ **车厢 Olivet / Sinai 和上下站的真实尺寸**。现在是估的。可以从 HAER/HABS（Library of Congress）、Angels Flight 官网或 1996 年重建的资料里找。
- [ ] ⭐ 车厢的配色（橙 + 黑）、分级车厢的台阶形外形、下站 Beaux-Arts 拱门的细节。
- [ ] ⭐ 轨道中段的错车段（测绘图上能看到三组轨道线）。
- [ ] ⭐ 用 LiDAR 做一个横剖面，再核对一次轨道的水平位置，现在估计误差在 1–2 m 以内。

## 5. 地形与场地细节

- [ ] ⭐⭐ **从 Wood Plot Plan 提取更多现状要素**。它是矢量图，已经对位好了（`data/plotplan_georef.json`）。可以提取：沿 Hill St 的楼梯、挡土墙、小路、出入口周边的阶梯花坛。
- [ ] ⭐ 人行道和路缘石的高差（现在路面和人行道是连在一起的地形）。
- [ ] ⭐ 围栏（场地从 2013 年起就围起来了，对讲“场地现状”很重要）。

## 6. 周边建筑

- [ ] ⭐⭐ **重要邻居单独精修**：Grand Central Market、Bradbury Building、Two California Plaza、Omni Hotel、Colburn School。现在都是 LiDAR 分层体块。
- [ ] ⭐ 8 栋合并后还有少量问题边的建筑（不影响观看，网页要做剖切时才需要修）。
- [ ] ⭐ 扩大范围，把 The Broad、Walt Disney Concert Hall 纳入（你的描述里提到它们，但在现在的 800 m 范围外）。需要再下载一块 LiDAR 瓦片。
- [ ] ⭐ 部分 LARIAC 轮廓是 2008 年的，和 2023 年 LiDAR 对不上的地方（中位误差 0.7 m，57 栋误差超过 5 m），要逐栋核查。

## 7. 数据与地块

- [ ] ⭐⭐⭐ **确认 Y-1 的正式范围**：951 是 95,419 sqft，加上 952 是 96,012 sqft，EIR 写的是 97,631 sqft。要确认 952 算不算进去，或者 EIR 用的是另一份测量。
- [ ] ⭐⭐ 叠加 ZIMAS 的分区、容积率和高度限制，作为网页上的信息图层。
- [ ] ⭐ 地块信息弹窗的内容，可以接你现有的 Y-1 研究资料：时间线、法规、Stakeholder Register。

## 8. 网页查看器（下一个大阶段）

**显示模式路线图**
- 现阶段：**四种模式并行**，一键切换，相机保持不动（2026-10-05 起）：
  1. **Mesh**：Blender 模型；
  2. **Model points**：网页加载时从同一份 GLB 实时撒点生成，mesh 一改就自动同步；
  3. **LiDAR**：2023 年 USGS 实测点云，**保持未经处理的原始参照**。只有高度、分类、强度三种着色，不受图层开关影响，点击也不识别物体；
  4. **Linked LiDAR**：同一批 LiDAR 点贴上 Blender 物体标签，按图层统一着色（颜色在 `web/config.json` 的 `layers.*.color` 里改），图层开关生效，点击识别物体并高亮。以后“按物体替换”的功能都做在这个模式里，LiDAR 模式始终保持原样。
- 目标（以后优化成两种模式）：
  1. **较写实的 Blender mesh**：地形贴 NAIP 航拍图，PBR 材质，光照烘焙；
  2. **高精度点云，而且要能和 mesh 同步修改更新**。
- [ ] ⭐⭐⭐ **“按物体切分的 LiDAR 点云”方案**（实现目标 2；2026-10-05 取代原来按区域整块替换的“编辑区”方案）
  核心思路：以真实 LiDAR 为底，只在 Blender 里改动过的物体上用 mesh 替换。点云模式默认就有 LiDAR 的精细度，同时能跟着 Blender 更新。
  1. [x] （2026-10-05 完成：`lidar_labels.py`，9.9M 点 4.5 s；归不进物体的 `_other` 占 13%，主要是加密区外的树和车辆）**给每个 LiDAR 点贴物体标签**：物体名和 Blender 一致（`BLD_<id>`、`Tree_042`、`MOCA`、`AF_*`、`Metro_*`、`Terrain`）。按优先级判断：Landmarks → 树冠 → 建筑轮廓 → 地面。归不进任何物体的点（车、路灯等）标为 `_other`。标签也是点云的第一个扩展属性。网页上的图层开关同样作用于 LiDAR 点，点击 LiDAR 点可以看到它属于哪个物体。
  2. [ ] **全密度 + 分层加载**：现在网页每 3 个点取 1 个（330 万）。改用 COPC 或 Potree，显示 800 m 范围内全部约 1,000 万个点，近处多加载、远处少加载。
  3. [ ] **几何指纹 + 自动替换**：一键导出时记录每个物体的几何指纹（geometry hash），和上一次比对：
     - 新建的物体 → 从 mesh 撒点加入；
     - 删除的物体 → 删掉它的 LiDAR 点；
     - 修改过的物体 → 删掉原来的点，换成从新 mesh 撒的点；
     - 没动过的物体 → 保留真实 LiDAR 点。
  4. [ ] **模拟 LiDAR 风格的撒点**：从上方“打”虚拟激光，加测量噪声，约 15 点/m²，让新旧点混在一起看不出接缝。
  5. [ ] **接入现场采集**：以后 Y-1 现场用手机 LiDAR 或照片生成的点云 / Splat，作为同样带标签的图层叠加进来，补上航测看不到的立面、树下和挡土墙细部。
  - 背景：Poisson 实验（`site-model/experiments/`）证明航测 LiDAR 不适合整体直接转 mesh。树会熔成一片，建筑只剩屋顶皮，被遮挡的地方是破洞。所以要按物体分别处理。
- [ ] ⭐⭐⭐ **点云格式要支持扩展属性**（来自课程网站 t-SNE 页第 10 节 feature-field splatting 的思路）：
  - 每个点除了 xyz，还要能带任意数量的属性：分类、强度、来源（`lidar` / `mesh_sampled` / `edited`）、物体 ID（例如 `MOCA`、`AF_Track_Deck`、`Tree_042`，和 Blender 的物体名对应）、所属地块 APN、材质。
  - 以后加入的 CLIP/SAM 语义特征、t-SNE 聚类编号，也只是多加一个属性，格式不用改。
  - 网页的“着色模式”统一做成“选一个属性 → 映射成颜色”，新增属性就自动多一个模式。
  - 做法：属性用独立的二进制通道（每个属性一个文件或 COPC 的 extra bytes），另外用一个 `attributes.json` 描述每个属性的名称、类型和取值范围。现在的 `web/data/lidar_points.bin` 是固定的 8 字节记录，正式版要改成这种结构。
- [ ] ⭐⭐ **用模型给 feature splat 当“真值”**：以后给 Y-1 拍照训练 LangSplat 或 Feature 3DGS 时，把 splat 对位到场地坐标系，用 Blender 里的物体 ID（建筑、树、挡土墙、Metro 雨棚）去检验 splat 的语义聚类对不对。这正是 t-SNE 页建议的练习，我们多了一份逐个物体的标注。
- [ ] ⭐ 网页内容做三档阅读深度（参照课程网站的 Research / Student / ELI5），视觉风格和课程网站保持一致。
- [ ] ⭐ splat 图层的格式先保留接口，等选定方法再定。新方法（例如 2025 年的 Student Splatting and Scooping）常见查看器不一定支持。
- [ ] ⭐⭐ 点云着色：用 NAIP 航拍图（公有领域）给 LiDAR 点取真实颜色（这批 LiDAR 没有 RGB）。
- [ ] ⭐⭐ 点云变大（不抽稀、扩大范围）后改用 COPC 或 Potree 的分层加载格式；超过 100 MB 的文件放外部存储。
- [ ] ⭐⭐⭐ three.js 加载 `exports/context.glb`（需要 DRACOLoader）。
- [ ] ⭐⭐⭐ 图层开关：地形、建筑、树、地块、Landmarks。
- [ ] ⭐⭐ 预设视角：4th & Hill 路口、Angels Flight 上站、Grand Ave、俯视平面。
- [ ] ⭐⭐ 点击地块或建筑弹出信息。GLB 里已经带了 `apn`、`height_m`、`source` 等属性（glTF extras）。
- [ ] ⭐ 剖切或切片，用来看坡地的高差。
- [ ] ⭐ 测距和高差测量。

## 9. 工程化

**Blender 更新 → 网页同步（做 Site model viewer 时一起完成，之后要定期检查）**
- [ ] ⭐⭐⭐ **手动建模放在独立的 collection 里**：`Terrain`、`Buildings`、`Y1_Parcel`、`Landmarks`、`Trees` 是脚本生成的，重新运行 build 脚本时会被清空重建，在里面手改的东西会丢失。设计方案、手动精修的建筑放在新的 collection 里（例如 `Design`），脚本永远不碰它们。
  - 检查：每次重新运行 build 脚本前，确认手动内容不在上面这 5 个 collection 里。
- [ ] ⭐⭐⭐ **一键导出脚本**（`site-model/scripts/export_glb.py`，在 Blender 里运行）：把脚本生成的 collection 加上 `Design` 等手动 collection 一起导出到 `site-model/exports/context.glb`，导出设置固定（Draco 压缩、+Y Up、带 extras 属性），不用每次手动选。
  - 检查：新增的手动 collection 要能被导出；导出后在本地查看器里核对。
- [ ] ⭐⭐⭐ **GLB 只放一个位置**：GLB 存在 `site-model/exports/`，但 GitHub Pages 只发布 `web/`。修改 `.github/workflows/pages.yml`，部署时自动把 `site-model/exports/*.glb` 复制进发布的网页里，repo 里只保留一份 GLB。
  - 检查：合并 PR 后，线上网页加载的是最新的 GLB（看浏览器 Network 面板里 GLB 的请求和大小）。

- [x] ⭐⭐⭐ **建 git repo**，加 `README.md` 和 `CLAUDE.md`，写清朋友协作的规则：开分支、发 PR、不直接推到 main。（2026-10-05 完成：`RuiW0211/sci-arc-studio-fall2026`）
- [ ] ⭐⭐⭐ 邀请组员之前，在 GitHub 上打开 main 分支保护（必须通过 PR 才能合并）。
- [ ] ⭐⭐ **一键重建脚本**：依次运行 `fetch_data → lidar_dsm → lidar_tiers → prep_moca → prep_blender → prep_landmarks → prep_trees`，然后在 Blender 里运行 `build_blender → build_landmarks → build_trees`，再导出 GLB。
- [ ] ⭐⭐ `requirements.txt`：laspy[lazrs]、pymupdf、rasterio、shapely、pyproj、scipy、scikit-learn。laspy 和 pymupdf 目前是用 `pip --user` 装的。
- [ ] ⭐⭐ **大文件处理**：LAZ（67 MB）、各种 PDF 不放进 git，写一个下载脚本代替。GLB 目前 1.25 MB，可以直接放进 repo。
- [ ] ⭐ GitHub Pages 部署。

## 10. 远期

- [ ] ⭐⭐ **现场拍照生成 Gaussian Splat**：把 Y-1 核心区换成照片级效果。用场地上的固定物（Angels Flight 下站、Metro 桅杆、街角）做对位控制点。
- [ ] ⭐ Google Earth Studio 做网页开场的飞入视频（必须标注 Google 来源，不能从中提取 3D）。

---

## 版权提醒

`references/` 里的 EIR 附录、ArchEyes 和 SubwayNut 的图片、Getty 的照片都**只在本地当建模参考**，不能放进公开的网页或 repo。
可以公开的数据：USGS 3DEP（公有领域）、LA County GIS、OpenStreetMap（需要标注 © OpenStreetMap contributors）。
