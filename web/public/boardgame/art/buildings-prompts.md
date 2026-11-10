# Атласы реальных городских объектов

Режим: встроенный image_gen, генерация с transparent_background=true.
Два отдельных атласа 4×2, затем кодирование в WebP с сохранением alpha.
Это художественные миниатюры по мотивам реальных объектов, не обмерные модели.

## Общая часть промпта

Use case: stylized-concept. Production sprite atlas for an elegant Kazakh property boardgame. ONE 4-column 2-row grid, exactly EIGHT different real architectural landmarks as isolated detailed miniature diorama models. Fully transparent background. Equal cells, each whole building fits inside its cell with 12 percent transparent margin, aligned ground level, absolutely no overlaps across cells, no text labels or numbers. Elevated three-quarter architectural camera consistent across sprites, realistic architectural proportions and materials, warm afternoon natural light, rich detailed beautiful premium rendered models, NOT cartoons, NOT blocks. Restrained tiny landscaping at base, soft contact shadows. Emphasize recognizable authentic silhouette of the specified REAL buildings, do not replace with generic invented architecture. No fantasy domes on Soviet buildings.

## almaty-buildings-v1.webp

Location ALMATY Kazakhstan. Top row left to right: 1 Kok Tobe television tower, tall slim concrete communications tower with distinct disc observation rings, small wooded hill pedestal; 2 Medeu outdoor speed skating ice stadium, oval white ice rink with open grandstand and surrounding mountain pines; 3 Green Bazaar Almaty, recognizable broad low Soviet modernist green-roofed market building, central covered entry, produce stalls; 4 Hotel Kazakhstan Almaty, tall slender curved white modernist hotel slab with distinctive gold crown roof. Bottom row left to right: 5 Abay Opera Theatre Almaty, pale ochre neoclassical building with colonnaded portico; 6 Ascension Cathedral Almaty, ornate yellow and white wooden Russian Orthodox cathedral with colorful green and gold roofs; 7 Almaty-2 railway station, cream classical railway station facade with columns and central clock; 8 Central State Museum Almaty, low monumental pale blue and white building with large blue dome and broad entrance steps. Museum and hotel must retain real modernist architecture. Architectural miniature illustrations with realistic 3D depth and material detail.

## turkistan-buildings-v1.webp

Location TURKISTAN Kazakhstan. Top row left to right: 1 Khoja Ahmed Yasawi Mausoleum, huge authentic rectangular sand brick mass, monumental unfinished high entrance portal and large ribbed turquoise dome behind; 2 Rabia Sultan Begim Mausoleum, modest five-room brick structure with tall pointed entrance and blue ribbed dome on cylindrical drum; 3 Karavansaray Turkistan waterfront complex, tan Silk Road arched facades around small turquoise canal and bridge; 4 Altyn Samruk flying theatre in Karavansaray, distinctive modern enormous golden egg enclosed by nestlike bronze organic ribs above glazed base. Bottom row left to right: 5 Turkistan railway station historic low white and ochre railway building with arched windows and decorative central portal; 6 historic oriental bathhouse Hammam by Yasawi complex, low tan brick bathhouse with several small shallow brick domes and simple arched entry; 7 Hilvet underground mosque entrance Turkistan, low tan brick single-domed structure with discreet underground stair entry, modest authentic form; 8 Azret Sultan historical area traditional brick fortress gateway, crenellated tan brick portal with blue tiled pointed arch. Faithfully recognizable archaeological and modern Kazakh architecture, no invented Western palaces, no generic interchangeable domes. Realistic 3D depth and material detail.

### Исправление прозрачности Туркестана

Edit target: this exact 4 column 2 row sprite atlas of 8 Turkistan buildings. Background extraction only. Remove ALL white/gray page background and subtle grid dividing lines, replace with true transparent alpha. Keep all 8 buildings, all materials colors and shapes, their base paving, landscaping, existing exact positions, same 4x2 regular grid, dimensions and relative sizes absolutely unchanged. Do not redesign, move, crop, or resize any object. Output genuinely transparent PNG cutout sprite atlas.

## Источники названий и городской архитектуры

- [Алматы: городской путеводитель](https://visitalmaty.kz/wp-content/themes/visitwp/media/putevoditel_po_Almaty.pdf)
- [Алматы: Панфилов и Жибек Жолы](https://www.gov.kz/memleket/entities/almaty-almaly/press/news/details/838176?lang=ru)
- [Туркестан: городской перечень улиц](https://www.gov.kz/org/turkestan-kalasy/documents/details/719489)
- [Зелёный базар](https://kazakhstan.travel/en/attractions/404)
- [Вознесенский собор](https://kazakhstan.travel/en/attractions/403)
- [Мавзолей Рабии Султан Бегим](https://azretsultan.kz/rus/mavzolej-rabiya-sultan-begim-hv-v/)

Порядок клеток — игровой маршрут, не географическая карта и не адресный справочник.
Улица без отдельного здания показывается дорожной миниатюрой; ей не приписывается чужой памятник.

## neighborhoods-v1.webp

Режим: встроенный image_gen, transparent_background=true.

Use case stylized-concept. Asset: ONE production 4 columns by 2 rows sprite atlas of EIGHT isolated realistic 3D miniature street scenes for a Kazakh city board game. Truly transparent background, no white background, no grid, no text, no captions, no overlaps between cells. Each entire streetscape stays centered in its own equal cell with clear transparent padding. Elevated camera about 30 degrees above horizon, three quarter view from side, consistent view for all sprites. Soft bright sunny daylight, rich realistic brick wood stucco and paving materials, beautiful detailed premium architectural model photography, not toy cubes or low poly icons. Each scene is a small living quarter with a short paved street or walkway, two or three small facades, trees, a bench and a street lamp. NO standalone road tile, NO gray square platform, NO thick slab base. Irregular organic grass and cobblestone edges fade to transparency. No people, no real readable signage, no fantasy skyscrapers. Top row is ALMATY inspired real local urban character, left-to-right: 1 pedestrian Panfilov street quarter with mature plane trees and pastel early 20th century facades; 2 Abay avenue quarter with ochre Soviet neoclassical facades and planted boulevard; 3 Gogol street quarter with low historic cream wooden house, small blue shutters and lush trees; 4 Dostyk avenue quarter with cream modernist apartment facades, bus stop and ornamental flower beds. Bottom row TURKISTAN real local urban character, left-to-right: 5 Zhibek Zholy street quarter with warm sand brick shops, textile awnings and poplar trees; 6 Sattarkhanov avenue quarter with contemporary white and tan civic facades and palms; 7 Kazybek bi street quarter with small tan stucco homes, blue gates and planted sidewalk; 8 Tauke Khan avenue quarter with local warm brick shops, a tea courtyard and tall poplars. These are illustrative streetscapes, retain realistic local city architectural character. No famous landmark replication needed. Separate 4x2 cutout sprites.

Кварталы — художественные примеры местной архитектуры. Они не утверждают точный адрес
конкретного кафе или дома на подписанной улице. Распределение вариантов задаёт street_sprite.
