#!/usr/bin/env sh


echo "Upload to PyPi"

while true; do
	read -p "Choose repo (pypi, testpypi): " -r choice
	case "$choice" in
		"pypi"|"testpypi")
			break
		;;
		*)
			echo "Wrong option"
		;;
	esac		
done

echo "For username, type __token__ if you want to use a token. You will only be asked if the information is not in the ~/.pypi file."

python3 -m twine upload --skip-existing --repository pypi dist/*

