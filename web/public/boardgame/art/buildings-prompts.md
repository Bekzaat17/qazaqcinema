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
