import os
import shutil

def copy_folder_contents(folder_src, folder_dest, update_queue):
    update_queue.put(f'Copying the content...')
    
    print(f"Starting to copy from {folder_src} to {folder_dest}")

    try:
        if not os.path.exists(folder_dest):
            os.makedirs(folder_dest)

        for item in os.listdir(folder_src):
            print(f"Copying item: {item}") 
            if item == '.git':
                continue  
            
            src_item = os.path.join(folder_src, item)
            dest_item = os.path.join(folder_dest, item)

            if os.path.isdir(src_item):
                shutil.copytree(src_item, dest_item)
            else:
                shutil.copy2(src_item, dest_item)

        update_queue.put(f"All contents from '{folder_src}' have been copied to '{folder_dest}' successfully.")
        print('Copy function executed fully')
        return 'copy function executed'

    except Exception as e:
        update_queue.put(f"An error occurred: {e}")
        print(f"Error during copying: {e}")
        print(f"Error in copying from {folder_src} to {folder_dest}")
