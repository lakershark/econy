import json

translations = {
    "Donald Trump is the war's biggest loser": ("特朗普是这场战争的最大输家", "他急于从伊朗脱身是有原因的"),
    "A ceasefire will not prevent the Iran war's economic harm": ("停火无法阻止伊朗战争的经济破坏", "即使霍尔木兹海峡重开，能源市场也将长期改变"),
    "Recriminations over Iran have heightened the risk of a break-up of NATO": ("伊朗战争的互相指责加剧了北约分裂的风险", "欧洲必须做好自我防卫的准备"),
    "Artemis II has offered Earth inspiration": ("阿尔忒弥斯二号为地球带来了激励", "但重燃的太空热情若要持续，需要新的基础"),
    "Sir Keir Starmer is Britain's best hope for legalising assisted dying": ("斯塔默是英国推动辅助死亡合法化的最大希望", "他应该停止拖延"),
    "Is Mexico's economy broken?": ("墨西哥经济已经崩溃了吗？", "本周还有：伊朗战争的代价、性工作者、旅游类型、职场无聊、气泡水"),
    "A plan for Europe's tech fightback": ("欧洲科技反击计划", "英国与欧盟若携手合作，可避免被远远甩在身后——尼克·克莱格爵士"),
    "America's war on Iran has changed the Middle East—for the worse": ("美国对伊朗的战争已改变了中东——向着更糟糕的方向", "本周停火让该地区比战争开始时更不安全"),
    "The war was steadily spiralling in scope and destruction": ("战争的规模与破坏程度在持续螺旋式上升", "美国、以色列和伊朗在不断扩大的区域内打击越来越多的目标"),
    "Donald Trump's ceasefire shows how America has changed": ("特朗普的停火协议揭示了美国的变化", "与老布什在科威特的胜利相比较"),
    "An environmentalist, a landowner and a libertarian walk into a barn": ("一位环保人士、一位地主和一位自由主义者走进谷仓", "一条输油管道如何搅乱了爱荷华州的政治联盟"),
    "Will California's next governor be a fighter or a fixer?": ("加州下任州长会是斗士还是修缮者？", "以全国知名度领先的候选人，胜过有地方政绩者"),
    "Meet the four Democratic tribes": ("认识民主党的四大派系", "1.9万名受访者揭示了左翼内部的对立派系"),
    "As more states legalise gambling, what next for Las Vegas?": ("随着更多州将赌博合法化，拉斯维加斯何去何从？", "游客数量下降，但合法化也带来了新机遇"),
    "That ugly ballroom epitomises the story of Donald Trump's presidency": ("那个丑陋的宴会厅浓缩了特朗普总统任期的故事", "它折射出其手段、方式与目标，揭示了其成就的真实本质"),
    "There is little prospect of legalising abortion in Brazil": ("巴西将堕胎合法化的前景渺茫", "拉丁美洲其他大国已将堕胎合法化或非刑事化"),
    "The strange, multicultural slang of Toronto's teenagers": ("多伦多青少年奇特的多元文化俚语", "伦敦说唱歌手有着不成比例的巨大影响力"),
    "The South American petro-state profiting from the Iran war": ("从伊朗战争中获益的南美石油国家", "这一繁荣正加剧石油财富吞噬经济的风险"),
    "How Pakistan emerged as an unlikely broker of peace in the Gulf": ("巴基斯坦如何出人意料地成为海湾和平调解人", "这个饱受困扰的国家巧妙地周旋于交战各方之间"),
    "A wary rapprochement between India and China": ("印中之间谨慎的和解", "印度新投资规则是一个审慎的开始"),
    "China may be building a big new airbase in the South China Sea": ("中国可能正在南海修建大型新空军基地", "但分析人士对时机和地点感到困惑"),
    "The tumbling rupee could be a big problem for Narendra Modi": ("卢比暴跌可能给莫迪带来大麻烦", "印度总理深知弱势货币的风险"),
    "India's religious minorities face harsher anti-conversion laws": ("印度宗教少数群体面临更严苛的反改宗法律", "挖坟事件加剧了宗教间的紧张关系"),
    "Cambodia honours a life-saving rat": ("柬埔寨为一只救命之鼠举行荣誉仪式", "这只啮齿动物帮助清除了逾百枚未爆地雷"),
    "Taiwan and China are preparing for a summit, of sorts": ("台湾与中国大陆正在筹备某种形式的峰会", "国民党领袖访问大陆之行暴露了党内裂痕"),
    "The West is doing more to combat China's covert activity abroad": ("西方正加大力度打击中国在海外的秘密活动", "但中国几乎没有收敛"),
    "AI micro-dramas are shaking up Chinese entertainment": ("AI微短剧正在颠覆中国娱乐产业", "监管机构威胁要搅局"),
    "Africa's protests span countries, classes and causes": ("非洲抗议浪潮跨越国界、阶层与诉求", "但能带来持久的改变吗？"),
    "Burkina Faso's government is committing war crimes": ("布基纳法索政府正在实施战争罪行", "在打击圣战主义的同时，它杀死的平民比圣战分子还多"),
    "A deadly conflict in Malawi raises questions about conservation": ("马拉维致命冲突引发对自然保护的质疑", "人类与野生动物如何共存？"),
    "How anarchist was Africa?": ("非洲曾有多无政府主义？", "前殖民时代的无国家状态或许是成功的标志，而非失败"),
    "European allies are losing hope of keeping America in NATO": ("欧洲盟友对留住美国留在北约已不抱希望", "特朗普对盟友拒绝协助其对伊朗开战勃然大怒"),
    "Most Syrians in Germany are there to stay": ("德国的大多数叙利亚人将留下来", "大规模遣返移民既愚蠢又不可能"),
    "Europe's joint nuclear-fusion project needs Russian expertise": ("欧洲联合核聚变项目离不开俄罗斯专业知识", "在ITER，俄西科学家仍在合作——尽管进展缓慢"),
    "Viktor Orban is bashing Ukraine for votes": ("欧尔班为了选票而痛批乌克兰", "匈牙利大选毒化了匈乌两国关系"),
    "How France learned to fight Russian disinformation": ("法国如何学会应对俄罗斯虚假信息", "这个欧盟受攻击最多的国家正在反击假新闻"),
    "Why a big country like Italy acts as if it were small": ("为何意大利这样的大国却表现得像个小国", "在特朗普与欧洲之间摇摆，契合其历史上的阵营转换传统"),
    "Why can't Britain pass an assisted-dying bill?": ("英国为何无法通过辅助死亡法案？", "一个立法失败的案例研究"),
    "Britain's government wants an important job to be done badly": ("英国政府希望一项重要工作做得差一些", "对移民劳动力的羞怯态度"),
    "Why Swindon is emerging as a centre for Britain's drone industry": ("斯温顿为何正在成为英国无人机产业中心", "如何打造产业集群"),
    "Gibraltar is resigned to a closer embrace with Spain": ("直布罗陀已接受与西班牙更紧密的相处", "关于这块英国飞地的新协议以短期代价换取长期收益"),
    "Britons are less bored than they used to be. This is bad": ("英国人比以前少了无聊感，这是一件坏事", "是时候重新发现无聊的价值了"),
    "Failing the Kanye test": ("没能通过坎耶测试", "这位美国说唱歌手将英国人的每一种神经质都推向了荒诞极端"),
    "Hospitals never recovered from covid-19": ("医院从未从新冠疫情中恢复过来", "它们深陷致命的恶性循环"),
    "When emigration helps bad rulers survive": ("当移民帮助了糟糕的统治者", "一本新书揭示大规模移民与全球民主倒退之间的关联"),
    "A giant succession wave is coming for family businesses": ("家族企业即将迎来大规模传承浪潮", "许多企业将无法存活"),
    "How war has made a 33-year-old the Czech Republic's richest man": ("战争如何让一位33岁的人成为捷克首富", "CSG的崛起：欧洲最新的国防巨头"),
    "Japan's mighty carmakers are in serious trouble": ("日本强大的汽车制造商陷入严重困境", "它们需要大胆的思维才能生存"),
    "How dangerous is Mythos, Anthropic's new AI model?": ("Anthropic的新AI模型Mythos有多危险？", "达里奥·阿莫迪的警告不应被忽视"),
    "Why McDonald's and KFC are growing like wildfire in China": ("麦当劳和肯德基为何在中国迅速扩张", "西方快餐品牌正在向农村地区延伸"),
    "The pros and cons of stretch goals": ("延伸目标的利与弊", "设定极具挑战性的目标会鼓励冒险——有好有坏"),
    "Every company is now a media company—and every boss a star": ("每家公司如今都是媒体公司，每位老板都是明星", "喋喋不休工业综合体的崛起"),
    "The third Gulf war will scar energy markets for a long time yet": ("第三次海湾战争将给能源市场留下长期创伤", "残余风险与受损基础设施将使价格长期居高"),
    "As Iran's civilian economy crumbles, its military economy grows stronger": ("伊朗民用经济崩溃，军事经济却日益壮大", "战争将这个国家一分为二"),
    "The latest Italian banking whodunnit has it all": ("最新意大利银行悬案应有尽有", "一场政变、一个阴谋，甚至还有一具尸体"),
    "Can the secondary market allay private-credit fears?": ("二级市场能否化解私人信贷的担忧？", "短期内有限，长期而言大有可为"),
    "Bye, bye to the Trump trades": ("特朗普交易，再见", "市场正在为许多与特朗普相关的押注画上句号"),
    "South Korea's AI industrial policy meets the energy shock": ("韩国AI产业政策遭遇能源冲击", "这场碰撞不会好看"),
    "One neat trick to end extreme poverty": ("终结极端贫困的一个巧妙方法", "一个古老的问题或许有出人意料的简单解决方案"),
    "AI models could offer mathematicians a common language": ("AI模型或许能为数学家提供共同语言", "有人希望它们能简化验证数学证明的过程"),
    "Mummified reptiles are revealing how breathing evolved": ("木乃伊化的爬行动物揭示了呼吸的演化", "这个问题此前悬而未决"),
    "Sir Demis Hassabis wants to automate drug design": ("德米斯·哈萨比斯爵士想让药物设计自动化", "我们与谷歌DeepMind的掌门人对话"),
    "Earth and Moon, then and now": ("地球与月球：昔日与今日", "阿尔忒弥斯二号的视角"),
    "Should you take multivitamins?": ("你应该服用复合维生素吗？", "研究表明某些人确实能从中受益"),
    "A third world war is plausible. Here's how to avoid one": ("第三次世界大战并非不可能，以下是避免之道", "关键在于理解大战可能偶然发生"),
    "He said he was an oligarch's son. The lie had tragic consequences": ("他自称是寡头之子，这个谎言酿成了悲剧", "帕特里克·拉登·基夫的新书探究一名青年之死与伦敦的地下世界"),
    "What's the most attractive genre of entertainment?": ("最迷人的娱乐类型是什么？", '全球数百万人热衷收看"美丽电视"'),
    "Why children become fussy eaters": ("孩子为何变成挑食者", "父母对糟糕建议的接受程度令人咋舌"),
    "The great comeback of cottage cheese": ("农家干酪的强势回归", "这种温和松散的食物正被健身男生和老奶奶们一同追捧"),
    "How Vladimir Putin's propaganda works": ("弗拉基米尔·普京的宣传机器如何运作", "俄罗斯已被逼疯，其他国家会遭受同样命运吗？"),
    "Semyon Gluzman defied the abuse of psychiatry by the USSR": ("谢苗·格鲁兹曼挑战苏联滥用精神病学的暴行", "这位精神科医生兼人权活动家于2月16日辞世，享年79岁"),
    "Politics": ("政治", "2026年4月9日"),
    "Business": ("商业", "2026年4月9日"),
    "The weekly cartoon": ("每周漫画", "2026年4月9日"),
    "Economic data, commodities and markets": ("经济数据、大宗商品与市场", "指标"),
}

def normalize(s):
    return s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')

with open('/Users/Nimmersatt/Documents/claude_projects/econy/data/economist/2026-04-11.json', encoding='utf-8') as f:
    issue = json.load(f)

matched = 0
for section in issue['toc']:
    for article in section['articles']:
        key = normalize(article['title'])
        if key in translations:
            article['title_zh'] = translations[key][0]
            article['subtitle_zh'] = translations[key][1]
            matched += 1

with open('/Users/Nimmersatt/Documents/claude_projects/econy/data/economist/2026-04-11.json', 'w', encoding='utf-8') as f:
    json.dump(issue, f, ensure_ascii=False, indent=2)

total = sum(len(s['articles']) for s in issue['toc'])
print(f'Translated {matched}/{total} article titles')
