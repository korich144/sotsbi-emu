#!/bin/bash

echo "Введите начальное значение t_id:"
read start_id

id=$start_id
while true; do
    echo "Запрос для t_id=$id"
    curl -H "Host: lrn.sotsbi.ru" \
         -H "Referer: http://lrn.sotsbi.ru/u700net.swf" \
         --compressed \
         "http://lrn.sotsbi.ru/getBgd.php?t_id=$id&s_hash=HjlNNnGnYj" \
         -o "$id" \
         --fail --silent --show-error

    if [ $? -eq 0 ]; then
        echo "Сохранено в файл $id"
    else
        echo "Ошибка при запросе t_id=$id"
    fi

    ((id++))
    echo "Нажмите любую клавишу для следующего запроса (Ctrl+C для выхода)..."
    read -n 1 -s
    echo
done