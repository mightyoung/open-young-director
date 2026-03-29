# Seedance 2.0 (wwwzhouhui) 研究报告

## 项目概览

**GitHub**: https://github.com/wwwzhouhui/seedance2.0
**Star**: 277 | **Fork**: 72
**描述**: 基于字节跳动即梦平台 Seedance 2.0 模型的 AI 视频生成 Web 应用，支持多图参考、双模型选择、6种画面比例、4-15秒时长

## 技术架构

- **前端**: React 19 + TypeScript + Vite + Tailwind CSS
- **后端**: Express.js + SQLite
- **部署**: Docker 支持一键部署

---

## 视频提示词结构分析

### Prompt 格式

```typescript
// PromptInput.tsx 中定义的占位符示例
const PLACEHOLDER =
  '上传 1-5 张参考图或视频，可自由组合人物、角色、道具、服装、场景等元素，定义他们之间的精彩互动。例如：@图片1作为首帧，@图片2作为尾帧，模仿@视频1的动作跳舞';
```

### 图片引用语法

支持两种格式引用参考图片：
- `@1`, `@2`, `@3` 等数字索引
- `@图片1`, `@图片2` 等中文格式

### Prompt 解析逻辑

`buildMetaListFromPrompt` 函数将 prompt 解析为 `meta_list`：

```typescript
function buildMetaListFromPrompt(prompt, imageCount) {
  const metaList = [];
  const placeholderRegex = /@(?:图 |image)?(\d+)/gi;

  // 解析出 text 和 image 两种 meta_type
  while ((match = placeholderRegex.exec(prompt)) !== null) {
    if (match.index > lastIndex) {
      const textBefore = prompt.substring(lastIndex, match.index);
      if (textBefore.trim()) {
        metaList.push({ meta_type: 'text', text: textBefore });
      }
    }
    const imageIndex = parseInt(match[1]) - 1;
    if (imageIndex >= 0 && imageIndex < imageCount) {
      metaList.push({
        meta_type: 'image',
        text: '',
        material_ref: { material_idx: imageIndex },
      });
    }
    lastIndex = match.index + match[0].length;
  }
  return metaList;
}
```

**meta_list 结构**:
- `meta_type: 'text'` - 文本片段
- `meta_type: 'image'` - 图片引用，包含 `material_ref.material_idx`

---

## 时间建模 (Temporal Modeling)

### 视频时长参数

```typescript
type Duration = 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15;
// 时长选项: 4-15 秒
```

### 帧率与时间戳

```typescript
fps: 24,                                    // 固定帧率 24fps
duration_ms: actualDuration * 1000,         // 毫秒单位
```

### 轮询机制

生成请求提交后，通过轮询 `get_history_by_ids` 接口检查状态：
- 状态 20: 生成中，继续等待
- 状态 30: 失败
- 最大重试 60 次，约 20 分钟超时

---

## 角色动画 (Character Animation)

### 参考模式

```typescript
type ReferenceMode = '全能参考' | '首帧参考' | '尾帧参考';
```

| 模式 | 说明 |
|------|------|
| 全能参考 | 音视频图均可参考，Omni Reference 模式 |
| 首帧参考 | 第一帧作为视频起始 |
| 尾帧参考 | 最后一帧作为视频结尾 |

### 角色动画实现

通过 `material_list` 和 `meta_list` 实现多参考图的角色动画：

```typescript
unified_edit_input: {
  material_list: materialList,  // 上传的参考图片
  meta_list: metaList,          // 解析后的 prompt 元数据
}
```

**material_list 结构**:
```typescript
{
  type: '',
  id: generateUUID(),
  material_type: 'image',
  image_info: {
    type: 'image',
    source_from: 'upload',
    platform_type: 1,
    image_uri: img.uri,          // ImageX CDN 上传后的 URI
    width: img.width,
    height: img.height,
  }
}
```

---

## 相机运动 (Camera Movement)

### 画面比例选项

```typescript
const VIDEO_RESOLUTION = {
  '1:1':  { width: 720,  height: 720  },
  '4:3':  { width: 960,  height: 720  },
  '3:4':  { width: 720,  height: 960  },
  '16:9': { width: 1280, height: 720  },
  '9:16': { width: 720,  height: 1280 },
  '21:9': { width: 1680, height: 720  },
};
```

### 纵横比计算

```typescript
const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));
const divisor = gcd(width, height);
const aspectRatio = `${width / divisor}:${height / divisor}`;
// 例如 16:9 -> 16:9, 4:3 -> 4:3
```

---

## 特殊参数

### 模型选择

```typescript
const MODEL_MAP = {
  'seedance-2.0':      'dreamina_seedance_40_pro',      // 专业版
  'seedance-2.0-fast': 'dreamina_seedance_40',          // 快速版
};

const BENEFIT_TYPE_MAP = {
  'seedance-2.0':      'dreamina_video_seedance_20_pro',
  'seedance-2.0-fast': 'dreamina_video_seedance_20_fast',
};
```

### 随机种子

```typescript
seed: Math.floor(Math.random() * 1000000000),
// 0-10亿随机种子，用于生成可复现的结果
```

### 视频生成参数

```typescript
video_gen_inputs: [{
  video_mode: 2,              // 视频模式 (2=生成模式)
  fps: 24,                    // 帧率
  duration_ms: 6000,          // 时长(毫秒)
  idip_meta_list: [],         // 空数组
  model_req_key: modelId,     // 模型请求键
  priority: 0,                // 优先级
  seed: randomSeed,           // 随机种子
}]
```

### AWS 签名 (ImageX CDN 上传)

使用 AWS4-HMAC-SHA256 签名访问字节 ImageX CDN：
```typescript
createAWSSignature(
  method, url, headers,
  access_key_id, secret_access_key, session_token, payload
)
```

---

## API 请求结构

### 生成视频请求 (`/mweb/v1/aigc_draft/generate`)

```typescript
const generateBody = {
  extend: {
    root_model: modelId,           // dreamina_seedance_40_pro
    m_video_commerce_info: {
      benefit_type: benefitType,   // dreamina_video_seedance_20_pro
      resource_id: 'generate_video',
    }
  },
  submit_id: submitId,             // UUID
  draft_content: JSON.stringify({
    type: 'draft',
    main_component_id: componentId,
    component_list: [{
      type: 'video_base_component',
      generate_type: 'gen_video',
      abilities: {
        gen_video: {
          text_to_video_params: {
            video_gen_inputs: [{ ... }],
            video_aspect_ratio: aspectRatio,
            seed: randomSeed,
          }
        }
      }
    }]
  })
};
```

---

## 关键发现总结

### 1. Prompt 结构特点
- **最大长度**: 5000 字符
- **图片引用**: `@数字` 或 `@图片+数字` 语法
- **混合内容**: 支持文本描述与图片引用的自由组合
- **默认值处理**: 无 prompt 时自动生成"使用图片1和图片2...图片生成视频"

### 2. 时间控制
- **时长范围**: 4-15 秒
- **固定帧率**: 24 FPS
- **超时设置**: 约 20 分钟轮询超时

### 3. 参考机制
- **Omni Reference (全能参考)**: 最强大的参考模式，支持图片、视频、音频的混合参考
- **首帧/尾帧参考**: 简化的时间点参考
- **最多 5 张参考图**: material_list 最多 5 个元素

### 4. 画面配置
- **6 种比例**: 1:1, 4:3, 3:4, 16:9, 9:16, 21:9
- **分辨率**: 720p 基础，16:9 最大 1280x720
- **纵横比**: 自动约分 (如 1280:720 -> 16:9)

### 5. 技术亮点
- **Playwright 代理**: 绕过即梦 shark 反爬机制
- **a_bogus 签名注入**: 自动生成签名绕过检测
- **ImageX CDN**: 阿里云 ImageX 全球 CDN 加速
- **会话管理**: 基于 sessionid 的认证体系

---

## 对 young-writer 系统的启示

1. **Prompt 解析**: 可借鉴 `buildMetaListFromPrompt` 的解析逻辑处理多模态输入
2. **时间控制**: 参考时长参数化设计 (4-15秒可配置)
3. **参考模式**: Omni Reference 概念可用于多图/视频融合生成
4. **图片引用**: `@N` 语法简洁有效，值得在内容生成系统中采用
